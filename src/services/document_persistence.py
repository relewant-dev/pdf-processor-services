from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx

from config import (
    QDRANT_CANDIDATES_COLLECTION,
    QDRANT_INSURANCES_COLLECTION,
    QDRANT_TIMEOUT_SECONDS,
    QDRANT_URL,
)


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
    email = _extract_first(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", document_text)
    phone = _extract_first(r"\+?[0-9][0-9\s().-]{6,}[0-9]", document_text)
    lines = [line.strip() for line in document_text.splitlines() if line.strip()]
    full_name = lines[0] if lines else ""
    first_name, last_name = _split_name(full_name)

    return {
        "id": str(uuid.uuid4()),
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "phone": phone,
        "seniority": _detect_seniority(document_text),
        "competences": {},
        "previous_works": [],
        "education": [],
        "raw_text": document_text,
        "created_at": _utc_timestamp(),
        "updated_at": _utc_timestamp(),
    }


def build_insurance_payload(document_text: str) -> dict[str, Any]:
    policy_number = _extract_first(
        r"(?:policy|insurance)\s*(?:number|no\.?|#)\s*[:\-]?\s*([A-Za-z0-9-]+)",
        document_text,
        capture_group=1,
    )
    provider_name = _extract_first(
        r"(?:provider|insurer|company)\s*[:\-]\s*([^\n]+)",
        document_text,
        capture_group=1,
    ) or "unknown"

    return {
        "id": str(uuid.uuid4()),
        "insurance_number": policy_number or f"unknown-{uuid.uuid4().hex[:12]}",
        "insurance_type": _detect_insurance_type(document_text),
        "provider_name": provider_name.strip(),
        "status": _detect_insurance_status(document_text),
        "coverage_details": {},
        "documents": [],
        "raw_text": document_text,
        "created_at": _utc_timestamp(),
        "updated_at": _utc_timestamp(),
    }


async def persist_document_if_supported(document_text: str, question: str) -> str:
    domain = infer_pdf_domain(document_text, question)
    if domain == "cv":
        await _upsert_payload(
            QDRANT_CANDIDATES_COLLECTION,
            build_candidate_payload(document_text),
        )
    elif domain == "insurance":
        await _upsert_payload(
            QDRANT_INSURANCES_COLLECTION,
            build_insurance_payload(document_text),
        )
    return domain


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


def _qdrant_point_id(value: str) -> int:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]
    return int(digest, 16)


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
