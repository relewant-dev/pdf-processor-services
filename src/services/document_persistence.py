from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Literal

import httpx
from fastmcp.exceptions import ToolError
from pydantic import BaseModel, ConfigDict, Field

from clients.ollama import chat_with_ollama
from config import (
    QDRANT_CANDIDATES_COLLECTION,
    QDRANT_INSURANCES_COLLECTION,
    QDRANT_TIMEOUT_SECONDS,
    QDRANT_URL,
    SERVICE_NAME,
)

logger = logging.getLogger(SERVICE_NAME)

MetadataKind = Literal["candidate", "insurance"]


class CandidateVectorMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    document_hash: str | None = None
    raw_text: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    phone: str | None = None
    seniority: str | None = None
    city: str | None = None
    country: str | None = None
    address: str | None = None
    competences: list[Any] = Field(default_factory=list)
    previous_works: list[Any] = Field(default_factory=list)
    education: list[Any] = Field(default_factory=list)
    current_job_title: str | None = None
    current_company: str | None = None
    availability_date: str | None = None
    notes: str | None = None
    language: str | None = None
    certifications: list[Any] = Field(default_factory=list)


class InsuranceVectorMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    document_hash: str | None = None
    raw_text: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    insurance_number: str | None = None
    insurance_type: str | None = None
    provider_name: str | None = None
    status: str | None = None
    coverage_details: dict[str, Any] = Field(default_factory=dict)
    documents: list[Any] = Field(default_factory=list)


METADATA_MODELS: dict[MetadataKind, type[BaseModel]] = {
    "candidate": CandidateVectorMetadata,
    "insurance": InsuranceVectorMetadata,
}

LIST_FIELDS: dict[MetadataKind, set[str]] = {
    "candidate": {"competences", "previous_works", "education", "certifications"},
    "insurance": {"documents"},
}

DICT_FIELDS: dict[MetadataKind, set[str]] = {
    "candidate": set(),
    "insurance": {"coverage_details"},
}


def infer_pdf_domain(document_text: str, question: str) -> str:
    corpus = f"{question}\n{document_text}".lower()
    insurance_keywords = (
        "policy",
        "insurance",
        "coverage",
        "premium",
        "beneficiary",
        "claim",
        "provider",
    )
    cv_keywords = (
        "curriculum vitae",
        "resume",
        "work experience",
        "education",
        "skills",
        "certification",
    )
    if any(keyword in corpus for keyword in insurance_keywords):
        return "insurance"
    if any(keyword in corpus for keyword in cv_keywords):
        return "cv"
    return "other"


def build_candidate_payload(document_text: str) -> dict[str, Any]:
    document_hash = _document_hash(document_text)
    email = _extract_first(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", document_text
    )
    phone = _extract_first(r"\+?[0-9][0-9\s().-]{6,}[0-9]", document_text)
    lines = [line.strip() for line in document_text.splitlines() if line.strip()]
    full_name = lines[0] if lines else ""
    first_name, last_name = _split_name(full_name)

    return {
        "id": f"candidate-{document_hash}",
        "document_hash": document_hash,
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "phone": phone,
        "seniority": _detect_seniority(document_text),
        "competences": [],
        "previous_works": [],
        "education": [],
        "raw_text": document_text,
        "created_at": _utc_timestamp(),
        "updated_at": _utc_timestamp(),
    }


def build_insurance_payload(document_text: str) -> dict[str, Any]:
    document_hash = _document_hash(document_text)
    policy_number = _extract_first(
        r"(?:policy|insurance)\s*(?:number|no\.?|#)\s*[:\-]?\s*([A-Za-z0-9-]+)",
        document_text,
        capture_group=1,
    )
    provider_name = (
        _extract_first(
            r"(?:provider|insurer|company)\s*[:\-]\s*([^\n]+)",
            document_text,
            capture_group=1,
        )
        or "unknown"
    )

    return {
        "id": f"insurance-{document_hash}",
        "document_hash": document_hash,
        "insurance_number": policy_number or f"unknown-{document_hash[:12]}",
        "insurance_type": _detect_insurance_type(document_text),
        "provider_name": provider_name.strip(),
        "status": _detect_insurance_status(document_text),
        "coverage_details": {},
        "documents": [],
        "raw_text": document_text,
        "created_at": _utc_timestamp(),
        "updated_at": _utc_timestamp(),
    }


def build_vector_db_metadata(
    payload: dict[str, Any], metadata_kind: MetadataKind
) -> dict[str, Any]:
    """Validate extracted metadata and return a Qdrant-safe dictionary."""
    metadata_model = METADATA_MODELS[metadata_kind]
    return metadata_model.model_validate(payload).model_dump(mode="json")


async def extract_payload_with_ollama(
    document_text: str,
    metadata_kind: MetadataKind,
) -> dict[str, Any]:
    """Extract structured metadata with Ollama while keeping Pydantic validation."""
    prompt = _build_metadata_extraction_prompt(document_text, metadata_kind)
    metrics = {"metadata_prompt_chars": len(prompt)}

    ollama_started_at = perf_counter()
    raw_response = await chat_with_ollama(prompt, response_format="json")
    metrics["metadata_ollama_duration_ms"] = _elapsed_ms(ollama_started_at)
    metrics["metadata_raw_response_chars"] = len(raw_response)

    parse_validate_started_at = perf_counter()
    parsed_payload = _parse_json_object(raw_response)
    normalized_payload = _normalize_extracted_payload(parsed_payload, metadata_kind)
    validated_payload = build_vector_db_metadata(normalized_payload, metadata_kind)
    metrics["metadata_parse_validate_duration_ms"] = _elapsed_ms(
        parse_validate_started_at
    )
    logger.info(
        "metadata_extraction_completed metadata_kind=%s %s",
        metadata_kind,
        " ".join(f"{key}={value}" for key, value in metrics.items()),
    )
    return validated_payload


def _build_metadata_extraction_prompt(
    document_text: str, metadata_kind: MetadataKind
) -> str:
    if metadata_kind == "candidate":
        contract = "\n".join(
            (
                "Expected JSON keys: id, first_name, last_name, email, phone, "
                "seniority, city, country, address, competences, previous_works, "
                "education, current_job_title, current_company, availability_date, "
                "notes, language, certifications.",
                "Use strings or null for scalar fields.",
                "Use arrays for competences, previous_works, education, and "
                "certifications; use [] when no evidence exists.",
                "Capture only evidence from the document; do not infer unsupported facts.",
            )
        )
    else:
        contract = "\n".join(
            (
                "Expected JSON keys: id, insurance_number, insurance_type, "
                "provider_name, status, coverage_details, documents.",
                "Use strings or null for scalar fields.",
                "Use an object for coverage_details and an array for documents; "
                "use {} or [] when no evidence exists.",
                "Capture only evidence from the document; do not infer unsupported facts.",
            )
        )

    return (
        f"Extract {metadata_kind} metadata from the document.\n"
        "Return only valid JSON. Do not include markdown, comments, or explanations.\n"
        "Omit these service-owned fields or set them null: id, document_hash, "
        "raw_text, created_at, updated_at.\n"
        f"{contract}\n\n"
        "Document text:\n"
        f"{document_text}"
    )


def _normalize_extracted_payload(
    payload: dict[str, Any], metadata_kind: MetadataKind
) -> dict[str, Any]:
    """Fill missing metadata fields before Pydantic validation."""
    metadata_model = METADATA_MODELS[metadata_kind]
    normalized = dict(payload)
    for field_name in metadata_model.model_fields:
        if field_name in normalized:
            continue
        if field_name in LIST_FIELDS[metadata_kind]:
            normalized[field_name] = []
        elif field_name in DICT_FIELDS[metadata_kind]:
            normalized[field_name] = {}
        else:
            normalized[field_name] = None
    return normalized


def _with_service_metadata(
    payload: dict[str, Any], metadata_kind: MetadataKind, document_text: str
) -> dict[str, Any]:
    document_hash = _document_hash(document_text)
    service_payload = dict(payload)
    now = _utc_timestamp()
    service_payload.update(
        {
            "id": f"{metadata_kind}-{document_hash}",
            "document_hash": document_hash,
            "raw_text": document_text,
            "created_at": now,
            "updated_at": now,
        }
    )
    return service_payload


async def persist_document_if_supported(document_text: str, question: str) -> str:
    workflow_metrics: dict[str, int] = {}
    domain = infer_pdf_domain(document_text, question)
    if domain == "cv":
        payload = build_candidate_payload(document_text)
        await _upsert_payload_if_new(QDRANT_CANDIDATES_COLLECTION, payload)
    elif domain == "insurance":
        payload = build_insurance_payload(document_text)
        await _upsert_payload_if_new(QDRANT_INSURANCES_COLLECTION, payload)
    logger.info(
        "document_database_workflow_completed domain=%s %s",
        domain,
        " ".join(f"{key}={value}" for key, value in workflow_metrics.items()),
    )
    return domain


async def _upsert_payload_if_new(collection_name: str, payload: dict[str, Any]) -> None:
    if await _document_exists(collection_name, payload):
        return

    await _upsert_payload(collection_name, payload)


async def _document_exists(collection_name: str, payload: dict[str, Any]) -> bool:
    body = {
        "filter": {
            "should": [
                {
                    "key": "document_hash",
                    "match": {"value": payload["document_hash"]},
                },
                {
                    "key": "raw_text",
                    "match": {"value": payload["raw_text"]},
                },
            ]
        },
        "limit": 1,
        "with_payload": False,
        "with_vector": False,
    }
    timeout = httpx.Timeout(QDRANT_TIMEOUT_SECONDS)
    async with httpx.AsyncClient(base_url=QDRANT_URL, timeout=timeout) as client:
        response = await client.post(
            f"/collections/{collection_name}/points/scroll", json=body
        )
        response.raise_for_status()

    points = response.json().get("result", {}).get("points", [])
    return bool(points)


async def _upsert_payload(collection_name: str, payload: dict[str, Any]) -> None:
    point_id = _qdrant_point_id(payload["id"])
    body = {
        "points": [
            {
                "id": point_id,
                "vector": [0.0],
                "payload": payload,
            }
        ]
    }
    timeout = httpx.Timeout(QDRANT_TIMEOUT_SECONDS)
    async with httpx.AsyncClient(base_url=QDRANT_URL, timeout=timeout) as client:
        await client.put(f"/collections/{collection_name}/points", json=body)


def _parse_json_object(raw_response: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise ToolError("Ollama returned invalid JSON for metadata extraction.") from exc
    if not isinstance(parsed, dict):
        raise ToolError("Ollama metadata extraction must return a JSON object.")
    return parsed


def _elapsed_ms(started_at: float) -> int:
    return int((perf_counter() - started_at) * 1000)


def _qdrant_point_id(value: str) -> int:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]
    return int(digest, 16)


def _document_hash(document_text: str) -> str:
    normalized_text = "\n".join(
        line.strip() for line in document_text.splitlines() if line.strip()
    )
    return hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()


def _extract_first(pattern: str, text: str, capture_group: int = 0) -> str | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None
    return match.group(capture_group).strip()


def _split_name(full_name: str) -> tuple[str, str]:
    parts = [part for part in full_name.split() if part]
    if len(parts) >= 2:
        return parts[0], " ".join(parts[1:])
    if len(parts) == 1:
        return parts[0], ""
    return "unknown", "unknown"


def _detect_seniority(text: str) -> str:
    lowered = text.lower()
    for level in ("lead", "senior", "mid", "junior"):
        if level in lowered:
            return level
    return "unknown"


def _detect_insurance_type(text: str) -> str:
    lowered = text.lower()
    for insurance_type in ("health", "car", "life", "travel", "home"):
        if insurance_type in lowered:
            return insurance_type
    return "unknown"


def _detect_insurance_status(text: str) -> str:
    lowered = text.lower()
    for status in ("active", "expired", "suspended", "cancelled"):
        if status in lowered:
            return status
    return "unknown"


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()
