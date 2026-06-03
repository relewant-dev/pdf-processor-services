from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from clients.ollama import chat_with_ollama
from config import (
    QDRANT_CANDIDATES_COLLECTION,
    QDRANT_INSURANCES_COLLECTION,
    QDRANT_TIMEOUT_SECONDS,
    QDRANT_URL,
)


VECTOR_DB_CHUNK_SIZE = 4000


class VectorDbMetadataError(ValueError):
    """Raised when extracted metadata cannot be persisted to the vector DB."""


class CandidateVectorMetadata(BaseModel):
    """Validated candidate metadata produced by the extraction layer."""

    model_config = ConfigDict(extra="allow")

    id: str = Field(..., min_length=1)
    document_hash: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    phone: str | None = None
    seniority: str | None = None
    competences: dict[str, Any] | None = None
    previous_works: list[dict[str, Any]] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    certification: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    raw_text: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class InsuranceVectorMetadata(BaseModel):
    """Validated insurance metadata produced by the extraction layer."""

    model_config = ConfigDict(extra="allow")

    id: str = Field(..., min_length=1)
    document_hash: str | None = None
    candidate_id: str | None = None
    policy_number: str | None = None
    insurance_provider: str | None = None
    insurance_type: str | None = None
    policy_holder: dict[str, Any] | None = None
    coverage_details: dict[str, Any] | None = None
    start_date: str | None = None
    end_date: str | None = None
    premium_amount: float | None = None
    currency: str = "EUR"
    beneficiary: dict[str, Any] | None = None
    raw_text: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class VectorDbRecord(BaseModel):
    """A validated vector DB record ready to upsert."""

    model_config = ConfigDict(extra="forbid")

    id: int
    vector: list[float] = Field(min_length=1)
    payload: dict[str, Any]

    @field_validator("payload")
    @classmethod
    def payload_values_must_be_supported(cls, value: dict[str, Any]) -> dict[str, Any]:
        _validate_metadata_values(value)
        return value


async def persist_document_if_supported(document_text: str, question: str) -> str:
    domain = await infer_pdf_domain_with_ollama(document_text, question)
    if domain == "cv":
        extracted_payload = await build_payload_with_ollama(document_text, "candidate")
        await _upsert_payload(QDRANT_CANDIDATES_COLLECTION, extracted_payload)
    elif domain == "insurance":
        extracted_payload = await build_payload_with_ollama(document_text, "insurance")
        await _upsert_payload(QDRANT_INSURANCES_COLLECTION, extracted_payload)
    return domain


async def infer_pdf_domain_with_ollama(document_text: str, question: str) -> str:
    """Classify document persistence domain with Ollama instead of language-specific labels."""
    prompt = _build_domain_classification_prompt(document_text, question)
    raw_result = await chat_with_ollama(prompt)
    payload = _parse_json_object(raw_result)
    domain = str(payload.get("document_type", "")).strip().lower()
    if domain not in {"cv", "insurance", "other"}:
        raise VectorDbMetadataError(
            "Ollama document classification must return document_type as "
            "one of: cv, insurance, other."
        )
    return domain


async def build_payload_with_ollama(
    document_text: str, metadata_kind: str
) -> dict[str, Any]:
    """Ask Ollama to map multilingual document text to the configured DB fields."""
    schema = _metadata_schema(metadata_kind)
    prompt = _build_metadata_extraction_prompt(document_text, metadata_kind, schema)
    raw_result = await chat_with_ollama(
        prompt, response_format=schema.model_json_schema()
    )
    extracted_payload = _parse_json_object(raw_result)
    payload = _with_service_metadata(extracted_payload, document_text, metadata_kind)
    build_vector_db_metadata(payload, metadata_kind=metadata_kind)
    return payload


async def persist_extracted_payload(
    collection_name: str,
    extracted_payload: dict[str, Any],
    *,
    metadata_kind: str | None = None,
) -> None:
    """Persist already-extracted LLM payload metadata to the vector DB.

    The vector DB workflow validates and persists the metadata it receives. It does
    not infer or hardcode semantic metadata such as skills, candidate names,
    document types, or insurance types.
    """
    records = build_vector_db_records(extracted_payload, metadata_kind=metadata_kind)
    await _upsert_records(collection_name, records)


def build_vector_db_records(
    extracted_payload: dict[str, Any],
    *,
    metadata_kind: str | None = None,
) -> list[VectorDbRecord]:
    metadata = build_vector_db_metadata(
        extracted_payload, metadata_kind=metadata_kind
    )
    embedding_text = _embedding_text_from_payload(metadata)
    chunks = (
        [embedding_text]
        if metadata_kind == "insurance"
        else _split_embedding_text(embedding_text)
    )
    return [
        VectorDbRecord(
            id=_qdrant_point_id(
                _chunk_record_id(str(metadata["id"]), index, len(chunks))
            ),
            vector=_embedding_vector_for_text(chunk),
            payload=_metadata_for_chunk(metadata, index, len(chunks)),
        )
        for index, chunk in enumerate(chunks)
    ]


def build_vector_db_metadata(
    extracted_payload: dict[str, Any],
    *,
    metadata_kind: str | None = None,
) -> dict[str, Any]:
    schema = _metadata_schema(metadata_kind)
    try:
        metadata_model = schema.model_validate(extracted_payload)
    except ValidationError as exc:
        raise VectorDbMetadataError(str(exc)) from exc

    metadata = metadata_model.model_dump(mode="json")
    _validate_metadata_values(metadata)
    return metadata


def _build_domain_classification_prompt(document_text: str, question: str) -> str:
    return (
        "Classify the uploaded document for vector database persistence. "
        "The document can be written in any language. Use semantic meaning, not "
        "English labels. Return only one JSON object with this exact shape: "
        '{"document_type":"cv|insurance|other"}. '
        "Choose cv for CVs, resumes, curricula vitae, candidate profiles, or "
        "professional biographies. Choose insurance for policies, insurance "
        "certificates, coverage documents, claims documents, or related policy "
        "paperwork. Choose other when neither applies.\n\n"
        f"User question:\n{question}\n\nDocument text:\n{document_text}"
    )


def _build_metadata_extraction_prompt(
    document_text: str, metadata_kind: str, schema: type[BaseModel]
) -> str:
    json_schema = json.dumps(schema.model_json_schema(), indent=2, sort_keys=True)
    field_names = ", ".join(schema.model_fields)
    return (
        "You are an information extraction system.\n"
        "Extract values only if explicitly supported by the document.\n"
        "Do not infer or invent information.\n"
        "Return only valid JSON. Do not include Markdown, code fences, prose, "
        "comments, or extra text.\n"
        "Missing scalar values must be null. Missing arrays must be [].\n"
        "Populate all fields defined in the schema.\n"
        "The document may be written in any language. Use semantic meaning rather "
        "than field labels.\n"
        "Use the complete JSON Schema below as the field contract and output shape. "
        "Do not add fields that are not in the schema.\n"
        "For object fields, return null when the document does not explicitly "
        "support the object; otherwise include only explicitly supported nested "
        "values.\n"
        "Normalize explicitly stated dates to YYYY-MM-DD when possible; otherwise "
        "preserve the explicit date text. Normalize explicitly stated money amounts "
        "as numbers and currencies as ISO 4217 codes when possible.\n"
        "Service-owned fields (id, document_hash, raw_text, created_at, updated_at) "
        "should be null unless explicitly present in the document; the service may "
        "overwrite them after extraction.\n"
        f"Metadata kind: {metadata_kind}.\n"
        f"Required top-level fields to populate: {field_names}.\n\n"
        f"JSON Schema:\n{json_schema}\n\n"
        f"Document text:\n{document_text}"
    )


def _parse_json_object(raw_result: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw_result.strip())
    except json.JSONDecodeError as exc:
        raise VectorDbMetadataError(
            "Ollama returned metadata that was not valid JSON."
        ) from exc
    if not isinstance(parsed, dict):
        raise VectorDbMetadataError("Ollama metadata response must be a JSON object.")
    return parsed


def _with_service_metadata(
    extracted_payload: dict[str, Any], document_text: str, metadata_kind: str
) -> dict[str, Any]:
    payload = dict(extracted_payload)
    document_hash = _document_hash(document_text)
    timestamp = _utc_timestamp()
    payload["id"] = _service_document_id(payload.get("id"), document_hash, metadata_kind)
    payload["document_hash"] = document_hash
    payload["raw_text"] = document_text
    payload.setdefault("created_at", timestamp)
    payload.setdefault("updated_at", timestamp)
    return payload


def _service_document_id(value: Any, document_hash: str, metadata_kind: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if metadata_kind == "candidate":
        return f"candidate-{document_hash}"
    if metadata_kind == "insurance":
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"insurance:{document_hash}"))
    return document_hash


async def _upsert_payload(collection_name: str, payload: dict[str, Any]) -> None:
    metadata_kind = _metadata_kind_for_collection(collection_name)
    await persist_extracted_payload(collection_name, payload, metadata_kind=metadata_kind)


def _metadata_kind_for_collection(collection_name: str) -> str | None:
    if collection_name == QDRANT_CANDIDATES_COLLECTION:
        return "candidate"
    if collection_name == QDRANT_INSURANCES_COLLECTION:
        return "insurance"
    return None


async def _upsert_records(
    collection_name: str, records: list[VectorDbRecord]
) -> None:
    body = {"points": [record.model_dump(mode="json") for record in records]}
    timeout = httpx.Timeout(QDRANT_TIMEOUT_SECONDS)
    async with httpx.AsyncClient(base_url=QDRANT_URL, timeout=timeout) as client:
        await client.put(f"/collections/{collection_name}/points", json=body)


def _qdrant_point_id(value: str) -> int:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]
    return int(digest, 16)


def _document_hash(document_text: str) -> str:
    normalized_text = "\n".join(
        line.strip() for line in document_text.splitlines() if line.strip()
    )
    return hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _metadata_schema(metadata_kind: str | None) -> type[BaseModel]:
    if metadata_kind == "candidate":
        return CandidateVectorMetadata
    if metadata_kind == "insurance":
        return InsuranceVectorMetadata
    return GenericVectorMetadata


class GenericVectorMetadata(BaseModel):
    """Validated generic metadata produced by the extraction layer."""

    model_config = ConfigDict(extra="allow")

    id: str = Field(..., min_length=1)
    raw_text: str | None = None


def _embedding_text_from_payload(metadata: dict[str, Any]) -> str:
    raw_text = metadata.get("raw_text")
    if isinstance(raw_text, str) and raw_text:
        return raw_text
    return " ".join(str(value) for value in metadata.values() if value is not None)


def _split_embedding_text(text: str) -> list[str]:
    if not text:
        return [""]
    return [
        text[index : index + VECTOR_DB_CHUNK_SIZE]
        for index in range(0, len(text), VECTOR_DB_CHUNK_SIZE)
    ]


def _chunk_record_id(base_id: str, chunk_index: int, chunk_count: int) -> str:
    if chunk_count == 1:
        return base_id
    return f"{base_id}:chunk-{chunk_index}"


def _metadata_for_chunk(
    metadata: dict[str, Any], chunk_index: int, chunk_count: int
) -> dict[str, Any]:
    chunk_metadata = dict(metadata)
    if chunk_count > 1:
        chunk_metadata["chunk_index"] = chunk_index
        chunk_metadata["chunk_count"] = chunk_count
    return chunk_metadata


def _embedding_vector_for_text(_text: str) -> list[float]:
    return [0.0]


def _validate_metadata_values(metadata: dict[str, Any]) -> None:
    for key, value in metadata.items():
        if not isinstance(key, str) or not key:
            raise VectorDbMetadataError("metadata keys must be non-empty strings")
        _validate_metadata_value(key, value)


def _validate_metadata_value(key: str, value: Any) -> None:
    if value is None or isinstance(value, str | int | float | bool):
        return
    if isinstance(value, list):
        for item in value:
            _validate_metadata_value(key, item)
        return
    if isinstance(value, dict):
        _validate_metadata_values(value)
        return
    raise VectorDbMetadataError(
        f"metadata field '{key}' has unsupported value type "
        f"{type(value).__name__}"
    )
