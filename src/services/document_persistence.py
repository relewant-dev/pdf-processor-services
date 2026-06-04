from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

import httpx
from fastmcp.exceptions import ToolError
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from clients.ollama import chat_with_ollama
from config import (
    QDRANT_CANDIDATES_COLLECTION,
    QDRANT_INSURANCES_COLLECTION,
    QDRANT_TIMEOUT_SECONDS,
    QDRANT_URL,
)


VECTOR_DB_CHUNK_SIZE = 4000
DocumentDomain = Literal["cv", "insurance", "other"]
MetadataKind = Literal["candidate", "insurance"]


class VectorDbMetadataError(ValueError):
    """Raised when extracted metadata cannot be persisted to the vector DB."""


class CandidateVectorMetadata(BaseModel):
    """Candidate table payload used as the source of truth for CV answers."""

    model_config = ConfigDict(extra="allow")

    id: str = Field(..., min_length=1)
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    phone: str | None = None
    seniority: str | None = None
    city: str | None = None
    country: str | None = None
    address: str | None = None
    competences: dict[str, Any] | list[Any] | None = None
    previous_works: list[dict[str, Any]] = Field(default_factory=list)
    education: list[dict[str, Any]] | list[str] = Field(default_factory=list)
    current_job_title: str | None = None
    current_company: str | None = None
    availability_date: str | None = None
    notes: str | None = None
    language: str | list[str] | None = None
    certifications: list[str] | list[dict[str, Any]] = Field(default_factory=list)
    document_hash: str | None = None
    raw_text: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class InsuranceVectorMetadata(BaseModel):
    """Insurance table payload used as the source of truth for insurance answers."""

    model_config = ConfigDict(extra="allow")

    id: str = Field(..., min_length=1)
    candidate_id: str | None = None
    policy_number: str | None = None
    insurance_provider: str | None = None
    insurance_type: str | None = None
    policy_holder: dict[str, Any] | None = None
    coverage_details: dict[str, Any] | None = None
    start_date: str | None = None
    end_date: str | None = None
    premium_amount: float | None = None
    currency: str | None = None
    beneficiary: dict[str, Any] | None = None
    document_hash: str | None = None
    raw_text: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class GenericVectorMetadata(BaseModel):
    """Validated generic metadata produced by the extraction layer."""

    model_config = ConfigDict(extra="allow")

    id: str = Field(..., min_length=1)
    raw_text: str | None = None


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


class DocumentWorkflowResult(BaseModel):
    """Result of the database-first PDF processing workflow."""

    model_config = ConfigDict(extra="forbid")

    response: str
    document_type: DocumentDomain
    collection_name: str | None = None
    record_id: str | None = None
    record_existed: bool = False


async def answer_document_prompt_from_database(
    document_text: str, question: str
) -> DocumentWorkflowResult:
    """Run the single CV/insurance pipeline with the database as source of truth.

    The PDF text is used only to classify the document, compute the stable document
    hash, and extract structured data when the corresponding database record does
    not already exist. User-facing answers are generated exclusively from the
    retrieved database payload, never directly from the PDF text.
    """
    domain = await infer_pdf_domain_with_ollama(document_text, question)
    if domain == "other":
        raise ToolError("Uploaded PDF must be either a CV or an insurance document.")

    metadata_kind = _metadata_kind_for_domain(domain)
    collection_name = _collection_for_metadata_kind(metadata_kind)
    document_hash = _document_hash(document_text)

    record = await get_document_by_hash(collection_name, document_hash)
    record_existed = record is not None
    if record is None:
        extracted_payload = await extract_payload_with_ollama(document_text, metadata_kind)
        await _upsert_payload(collection_name, extracted_payload)
        record = await get_document_by_hash(collection_name, document_hash)
        if record is None:
            raise ToolError(
                "Document was saved but could not be retrieved from the database. "
                "Check Qdrant availability and collection indexing."
            )

    response = await build_answer_from_database_record(
        question=question,
        document_type=domain,
        record=record,
    )
    return DocumentWorkflowResult(
        response=response,
        document_type=domain,
        collection_name=collection_name,
        record_id=str(record.get("id")) if record.get("id") is not None else None,
        record_existed=record_existed,
    )


async def infer_pdf_domain_with_ollama(document_text: str, question: str) -> DocumentDomain:
    """Classify the uploaded PDF as cv, insurance, or other."""
    prompt = _build_domain_classification_prompt(document_text, question)
    raw_result = await chat_with_ollama(prompt)
    payload = _parse_json_object(raw_result)
    domain = str(payload.get("document_type", "")).strip().lower()
    if domain not in {"cv", "insurance", "other"}:
        raise VectorDbMetadataError(
            "Ollama document classification must return document_type as "
            "one of: cv, insurance, other."
        )
    return domain  # type: ignore[return-value]


async def extract_payload_with_ollama(
    document_text: str, metadata_kind: MetadataKind
) -> dict[str, Any]:
    """Extract structured database payload with Ollama for a new document only."""
    schema = _metadata_schema(metadata_kind)
    prompt = _build_metadata_extraction_prompt(document_text, metadata_kind, schema)
    raw_result = await chat_with_ollama(
        prompt, response_format=schema.model_json_schema()
    )
    extracted_payload = _parse_json_object(raw_result)
    payload = _with_service_metadata(extracted_payload, document_text, metadata_kind)
    build_vector_db_metadata(payload, metadata_kind=metadata_kind)
    return payload


async def build_answer_from_database_record(
    *, question: str, document_type: DocumentDomain, record: dict[str, Any]
) -> str:
    """Answer the prompt from structured database data only."""
    answer_payload = _database_answer_payload(record)
    prompt = _build_database_answer_prompt(question, document_type, answer_payload)
    return await chat_with_ollama(prompt)


async def get_document_by_hash(
    collection_name: str, document_hash: str
) -> dict[str, Any] | None:
    """Retrieve the first payload matching a document hash from the collection."""
    body = {
        "filter": {
            "must": [
                {"key": "document_hash", "match": {"value": document_hash}},
            ]
        },
        "limit": 1,
        "with_payload": True,
        "with_vector": False,
    }
    timeout = httpx.Timeout(QDRANT_TIMEOUT_SECONDS)
    async with httpx.AsyncClient(base_url=QDRANT_URL, timeout=timeout) as client:
        response = await client.post(
            f"/collections/{collection_name}/points/scroll", json=body
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ToolError(
                f"Failed to query Qdrant collection '{collection_name}' for existing document."
            ) from exc
        data = response.json()

    result = data.get("result", {})
    points = result.get("points", result if isinstance(result, list) else [])
    if not points:
        return None
    payload = points[0].get("payload", {})
    if not isinstance(payload, dict):
        raise ToolError("Qdrant returned a document payload with an unexpected shape.")
    return payload


async def persist_extracted_payload(
    collection_name: str,
    extracted_payload: dict[str, Any],
    *,
    metadata_kind: str | None = None,
) -> None:
    """Persist already-extracted metadata to the vector DB."""
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
        "Classify the uploaded document for database routing. "
        "The document can be written in any language. Use semantic meaning, not "
        "English labels. Return only one JSON object with this exact shape: "
        '{"document_type":"cv|insurance|other"}. '
        "Choose cv for CVs, resumes, curricula vitae, candidate profiles, or "
        "professional biographies. Choose insurance for policies, insurance "
        "certificates, coverage documents, claims documents, or related policy "
        "paperwork. Choose other when neither applies. Do not answer the user "
        "question and do not extract structured fields in this step.\n\n"
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


def _build_database_answer_prompt(
    question: str, document_type: DocumentDomain, record: dict[str, Any]
) -> str:
    database_json = json.dumps(record, indent=2, sort_keys=True, ensure_ascii=False)
    return (
        "Answer the user's question using only the structured database record below. "
        "The database is the single source of truth. Do not use or refer to the "
        "uploaded PDF text, and do not invent missing values. If the database record "
        "does not contain enough information, say which information is unavailable.\n\n"
        f"Document type: {document_type}\n"
        f"User question:\n{question}\n\n"
        f"Database record:\n{database_json}"
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
    payload["created_at"] = payload.get("created_at") or timestamp
    payload["updated_at"] = timestamp
    return payload


def _database_answer_payload(record: dict[str, Any]) -> dict[str, Any]:
    excluded_keys = {"raw_text", "document_hash", "chunk_index", "chunk_count"}
    return {key: value for key, value in record.items() if key not in excluded_keys}


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


def _metadata_kind_for_domain(domain: DocumentDomain) -> MetadataKind:
    if domain == "cv":
        return "candidate"
    if domain == "insurance":
        return "insurance"
    raise ToolError("Uploaded PDF must be either a CV or an insurance document.")


def _collection_for_metadata_kind(metadata_kind: MetadataKind) -> str:
    if metadata_kind == "candidate":
        return QDRANT_CANDIDATES_COLLECTION
    return QDRANT_INSURANCES_COLLECTION


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
        response = await client.put(
            f"/collections/{collection_name}/points",
            params={"wait": True},
            json=body,
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ToolError(f"Failed to upsert Qdrant collection '{collection_name}'.") from exc


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
