from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

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
    full_name = _extract_candidate_name(lines)
    first_name, last_name = _split_name(full_name)

    return {
        "id": f"candidate-{document_hash}",
        "document_hash": document_hash,
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "phone": phone,
        "seniority": _detect_seniority(document_text),
        "competences": _extract_candidate_competences(document_text),
        "previous_works": _extract_candidate_previous_works(document_text),
        "education": _extract_candidate_education(document_text),
        "certification": _extract_candidate_certifications(document_text),
        "languages": _extract_candidate_languages(document_text),
        "raw_text": document_text,
        "created_at": _utc_timestamp(),
        "updated_at": _utc_timestamp(),
    }


def build_insurance_payload(document_text: str) -> dict[str, Any]:
    document_hash = _document_hash(document_text)
    policy_number = _extract_first(
        r"(?:policy|insurance|certificate)\s*(?:number|no\.?|#)\s*[:\-]?\s*([A-Za-z0-9-]+)",
        document_text,
        capture_group=1,
    )
    premium_amount, premium_currency = _extract_money_components_for_label(
        document_text, ("premium", "amount due")
    )
    coverage_limit, _coverage_currency = _extract_money_components_for_label(
        document_text, ("coverage limit", "limit", "sum insured")
    )
    timestamp = _utc_timestamp()

    return {
        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"insurance:{document_hash}")),
        "document_hash": document_hash,
        "candidate_id": _extract_candidate_id(document_text),
        "policy_number": policy_number or f"unknown-{document_hash[:12]}",
        "insurance_provider": _extract_insurance_provider_name(document_text),
        "insurance_type": _detect_insurance_type(document_text),
        "policy_holder": _extract_person_name_json(
            _extract_first(
                r"(?:policyholder|policy holder|insured|member|name)\s*[:\-]\s*([^\n]+)",
                document_text,
                capture_group=1,
            )
        ),
        "coverage_details": _extract_insurance_coverage_details(
            document_text, coverage_limit=coverage_limit
        ),
        "start_date": _normalize_date(
            _extract_labeled_date(
                document_text, ("effective date", "start date", "valid from")
            )
        ),
        "end_date": _normalize_date(
            _extract_labeled_date(
                document_text,
                ("expiration date", "expiry date", "end date", "valid until"),
            )
        ),
        "premium_amount": premium_amount if premium_amount is not None else 0.0,
        "currency": (
            premium_currency or _extract_labeled_currency(document_text) or "EUR"
        ),
        "beneficiary": _extract_beneficiary(document_text),
        "raw_text": document_text,
        "created_at": timestamp,
        "updated_at": timestamp,
    }


async def persist_document_if_supported(document_text: str, question: str) -> str:
    domain = infer_pdf_domain(document_text, question)
    if domain == "cv":
        extracted_payload = build_candidate_payload(document_text)
        await _upsert_payload(QDRANT_CANDIDATES_COLLECTION, extracted_payload)
    elif domain == "insurance":
        extracted_payload = build_insurance_payload(document_text)
        await _upsert_payload(QDRANT_INSURANCES_COLLECTION, extracted_payload)
    return domain


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


def _extract_candidate_name(lines: list[str]) -> str:
    ignored_headings = {
        "curriculum vitae",
        "resume",
        "cv",
        "profile",
        "summary",
        "contact",
    }
    for line in lines[:8]:
        normalized = line.strip().lower().rstrip(":")
        if normalized in ignored_headings:
            continue
        if "@" in line or re.search(r"\d", line):
            continue
        if re.search(r"\b(phone|email|address|linkedin|github)\b", line, re.IGNORECASE):
            continue
        words = [word for word in re.split(r"\s+", line) if word]
        if 2 <= len(words) <= 5:
            return line
    return lines[0] if lines else ""


def _extract_candidate_education(text: str) -> list[str]:
    entries = _extract_section_entries(
        text,
        ("education", "academic background", "studies", "formation"),
        (
            "experience",
            "work experience",
            "professional experience",
            "employment",
            "skills",
            "technical skills",
            "competences",
            "certifications",
            "projects",
            "languages",
        ),
    )
    degrees = [_extract_degree(entry) for entry in entries]
    return _deduplicate_preserving_order([degree for degree in degrees if degree])


def _extract_candidate_certifications(text: str) -> list[str]:
    entries = _extract_section_lines(
        text,
        ("certifications", "certification", "certificates", "licenses", "licences"),
        (
            "experience",
            "work experience",
            "professional experience",
            "education",
            "skills",
            "technical skills",
            "competences",
            "projects",
            "languages",
        ),
    )
    certification_names = [
        name for entry in entries if (name := _extract_certification_name(entry))
    ]
    return _deduplicate_preserving_order(certification_names)


def _extract_candidate_languages(text: str) -> list[str]:
    entries = _extract_section_lines(
        text,
        ("languages", "language"),
        (
            "experience",
            "work experience",
            "professional experience",
            "education",
            "skills",
            "technical skills",
            "competences",
            "certifications",
            "projects",
        ),
    )
    return _clean_profile_list_entries(entries)


def _extract_candidate_previous_works(text: str) -> list[dict[str, str]]:
    entries = _extract_section_entries(
        text,
        ("experience", "work experience", "professional experience", "employment"),
        (
            "education",
            "skills",
            "technical skills",
            "competences",
            "certifications",
            "projects",
            "languages",
        ),
    )
    work_entries: list[dict[str, str]] = []
    for entry in entries:
        if not _looks_like_work_entry(entry):
            continue
        work_entries.append(
            _without_empty_values(
                {
                    "title": _extract_job_title(entry),
                    "company": _extract_company(entry),
                    "date_range": _extract_date_range(entry),
                    "description": entry,
                }
            )
        )
    return work_entries


def _extract_candidate_competences(text: str) -> dict[str, list[str]]:
    skills_text = "\n".join(
        _extract_section_entries(
            text,
            ("skills", "technical skills", "competences", "competencies"),
            (
                "experience",
                "work experience",
                "professional experience",
                "education",
                "certifications",
                "projects",
                "languages",
            ),
        )
    )
    corpus = skills_text or text
    technical_keywords = (
        "python",
        "java",
        "javascript",
        "typescript",
        "sql",
        "docker",
        "kubernetes",
        "aws",
        "azure",
        "gcp",
        "linux",
        "git",
        "react",
        "node",
        "fastapi",
        "django",
        "machine learning",
        "artificial intelligence",
        "data analysis",
    )
    listed_skills = _split_list_items(skills_text) if skills_text else []
    technical_keyword_map = {keyword.lower(): keyword for keyword in technical_keywords}
    listed_technical = [
        technical_keyword_map[skill.lower()]
        for skill in listed_skills
        if skill.lower() in technical_keyword_map
    ]
    technical = _deduplicate_preserving_order(
        listed_technical + _ordered_keyword_matches(corpus, technical_keywords)
    )
    custom = [
        skill
        for skill in listed_skills
        if skill.lower() not in {item.lower() for item in technical}
        and not re.search(
            r"\b(skills?|competences?|competencies)\b", skill, re.IGNORECASE
        )
    ]
    competences: dict[str, list[str]] = {}
    if technical:
        competences["technical"] = technical
    if custom:
        competences["other"] = custom[:20]
    return competences


def _extract_insurance_provider_name(text: str) -> str:
    explicit_provider = _extract_first(
        r"(?:provider|insurer|insurance company|company)\s*[:\-]\s*([^\n]+)",
        text,
        capture_group=1,
    )
    if explicit_provider:
        return explicit_provider.strip()

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines[:8]:
        if re.search(
            r"\b(insurance|assurance|mutual|life|health|casualty)\b",
            line,
            re.IGNORECASE,
        ):
            return line
    return "unknown"


def _extract_insurance_coverage_details(
    text: str, *, coverage_limit: float | None = None
) -> dict[str, Any]:
    details = _without_empty_values(
        {
            "coverage_limit": coverage_limit,
            "medical": _detect_coverage_flag(text, "medical"),
            "dental": _detect_coverage_flag(text, "dental"),
            "accident": _detect_coverage_flag(text, "accident"),
            "deductible": _extract_money_for_label(text, ("deductible", "excess")),
        }
    )
    coverages = _extract_coverage_lines(text)
    exclusions = _extract_exclusion_lines(text)
    if coverages:
        details["coverages"] = coverages
    if exclusions:
        details["exclusions"] = exclusions
    return details


def _extract_candidate_id(text: str) -> str | None:
    return _extract_first(
        r"candidate\s*(?:id|uuid)\s*[:\-]?\s*"
        r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
        r"[0-9a-f]{4}-[0-9a-f]{12})",
        text,
        capture_group=1,
    )


def _extract_person_name_json(full_name: str | None) -> dict[str, str] | None:
    if not full_name:
        return None
    cleaned = _strip_inline_metadata(full_name)
    first_name, last_name = _split_name(cleaned)
    if first_name == "unknown" and last_name == "unknown":
        return None
    return _without_empty_values({"first_name": first_name, "last_name": last_name})


def _extract_beneficiary(text: str) -> dict[str, str] | None:
    beneficiary_text = _extract_first(
        r"beneficiary\s*[:\-]\s*([^\n]+)", text, capture_group=1
    )
    if not beneficiary_text:
        return None
    relationship = _extract_first(
        r"relationship\s*[:\-]\s*([^,;\n]+)", beneficiary_text, capture_group=1
    )
    name = re.sub(
        r"\brelationship\s*[:\-]\s*[^,;\n]+", "", beneficiary_text, flags=re.IGNORECASE
    ).strip(" ,;|-\t")
    if not relationship:
        relation_match = re.search(
            r"(.+?)\s*[,;(]\s*(spouse|partner|child|parent|sibling|friend|other)\)?$",
            name,
            flags=re.IGNORECASE,
        )
        if relation_match:
            name = relation_match.group(1).strip()
            relationship = relation_match.group(2).strip().title()
    return _without_empty_values(
        {"name": _strip_inline_metadata(name), "relationship": relationship}
    )


def _strip_inline_metadata(value: str) -> str:
    return re.split(
        r"\s+(?:relationship|date|dob|birth|policy|coverage|premium)\s*[:\-]",
        value.strip(),
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip(" ,;|-\t")


def _detect_coverage_flag(text: str, label: str) -> bool | None:
    explicit = _extract_first(
        rf"\b{re.escape(label)}\b\s*[:\-]?\s*"
        r"(true|false|yes|no|covered|included|excluded|not covered)",
        text,
        capture_group=1,
    )
    if explicit:
        return explicit.lower() in {"true", "yes", "covered", "included"}
    if re.search(rf"\b{re.escape(label)}\b", text, flags=re.IGNORECASE):
        return True
    return None


def _extract_insurance_document_references(text: str) -> list[dict[str, str]]:
    references: list[dict[str, str]] = []
    for label, pattern in (
        (
            "endorsement",
            r"endorsement\s*(?:no\.?|number|#)?\s*[:\-]?\s*([A-Za-z0-9-]+)",
        ),
        (
            "certificate",
            r"certificate\s*(?:no\.?|number|#)?\s*[:\-]?\s*([A-Za-z0-9-]+)",
        ),
    ):
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            references.append({"type": label, "reference": match.group(1).strip()})
    return references


def _extract_section_lines(
    text: str, headings: tuple[str, ...], stop_headings: tuple[str, ...]
) -> list[str]:
    lines = [line.strip(" •-*\t") for line in text.splitlines()]
    entries: list[str] = []
    in_section = False

    for line in lines:
        heading_content = _extract_heading_content(line, headings)
        if heading_content is not None:
            in_section = True
            if heading_content:
                entries.append(heading_content)
            continue
        if in_section and _extract_heading_content(line, stop_headings) is not None:
            break
        if in_section and line.strip():
            entries.append(line.strip())

    return entries


def _extract_section_entries(
    text: str, headings: tuple[str, ...], stop_headings: tuple[str, ...]
) -> list[str]:
    lines = [line.strip(" •-*\t") for line in text.splitlines()]
    entries: list[str] = []
    in_section = False
    current: list[str] = []

    for line in lines:
        if not line.strip():
            if current:
                entries.append(" ".join(current).strip())
                current = []
            continue
        heading_content = _extract_heading_content(line, headings)
        if heading_content is not None:
            in_section = True
            if current:
                entries.append(" ".join(current).strip())
                current = []
            if heading_content:
                current.append(heading_content)
            continue
        if in_section and _extract_heading_content(line, stop_headings) is not None:
            break
        if not in_section:
            continue
        if _looks_like_new_entry(line) and current:
            entries.append(" ".join(current).strip())
            current = []
        current.append(line.strip())

    if current:
        entries.append(" ".join(current).strip())
    return [entry for entry in entries if entry]


def _heading_pattern(headings: tuple[str, ...]) -> str:
    return r"(?:" + "|".join(re.escape(heading) for heading in headings) + r")"


def _extract_heading_content(line: str, headings: tuple[str, ...]) -> str | None:
    stripped_line = line.strip()
    if not stripped_line:
        return None
    heading_pattern = _heading_pattern(headings)
    match = re.match(
        rf"^\s*{heading_pattern}\s*(?::\s*(.*))?$",
        stripped_line,
        flags=re.IGNORECASE,
    )
    if match:
        return (match.group(1) or "").strip()
    return None


def _looks_like_new_entry(line: str) -> bool:
    return bool(
        re.search(r"(?:19|20)\d{2}|present|current|ongoing", line, re.IGNORECASE)
        or re.match(r"[A-Z][A-Za-z .]+\s*[-–—|]", line)
    )


def _looks_like_work_entry(entry: str) -> bool:
    if re.search(
        r"\b(date of birth|place of birth|birth|nationality)\b", entry, re.IGNORECASE
    ):
        return False
    normalized_entry = _strip_leading_date_range(entry)
    if not re.search(r"[A-Za-z]", normalized_entry):
        return False

    work_terms = (
        "engineer",
        "developer",
        "manager",
        "analyst",
        "consultant",
        "intern",
        "designer",
        "specialist",
        "architect",
        "lead",
        "tutor",
        "teacher",
        "assistant",
        "researcher",
    )
    return any(term in normalized_entry.lower() for term in work_terms)


def _extract_degree(entry: str) -> str | None:
    degree_match = re.search(
        r"((?:B\.?Sc|M\.?Sc|MBA|PhD|Bachelor|Master|Doctorate|Diploma|Degree|Laurea)"
        r"[^,;|–—-]*)",
        entry,
        flags=re.IGNORECASE,
    )
    return degree_match.group(1).strip(" -–—|") if degree_match else None


def _extract_institution(entry: str) -> str | None:
    institution_match = re.search(
        r"(?:at|from|,|[-–—|])\s*([^,;|]+(?:University|College|Institute|School|Università|Politecnico)[^,;|]*)",
        entry,
        flags=re.IGNORECASE,
    )
    if institution_match:
        return institution_match.group(1).strip()
    university_match = re.search(
        r"([^,;|]*(?:University|College|Institute|School|Università|Politecnico)[^,;|]*)",
        entry,
        flags=re.IGNORECASE,
    )
    return university_match.group(1).strip() if university_match else None


def _extract_date_range(entry: str) -> str | None:
    date_pattern = _date_token_pattern()
    match = re.search(
        rf"({date_pattern})\s*(?:[-–—]|to)\s*({date_pattern})",
        entry,
        flags=re.IGNORECASE,
    )
    if match:
        return f"{match.group(1).strip()} - {match.group(2).strip()}"
    return None


def _date_token_pattern() -> str:
    return (
        r"(?:present|current|ongoing|"
        r"(?:19|20)\d{2}(?:[./-](?:1[0-2]|0?[1-9]))?|"
        r"(?:1[0-2]|0?[1-9])[./-](?:19|20)\d{2}|"
        r"(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+)?(?:19|20)\d{2})"
    )


def _strip_leading_date_range(entry: str) -> str:
    date_pattern = _date_token_pattern()
    return re.sub(
        rf"^\s*{date_pattern}\s*(?:[-–—]|to)\s*{date_pattern}\s*[,|:;-]?\s*",
        "",
        entry,
        count=1,
        flags=re.IGNORECASE,
    ).strip()


def _extract_job_title(entry: str) -> str | None:
    normalized_entry = _strip_leading_date_range(entry)
    if not normalized_entry or not re.search(r"[A-Za-z]", normalized_entry):
        return None
    title_match = re.match(
        r"(.+?)(?:\s+(?:[-–—|,]|at)\s+)",
        normalized_entry,
        flags=re.IGNORECASE,
    )
    if title_match:
        title = title_match.group(1).strip(" -–—|,")
        return title if not _looks_like_date_only(title) else None
    sentence_match = re.match(r"(.+?)(?:\s{2,}|\.\s|$)", normalized_entry)
    title = sentence_match.group(1).strip() if sentence_match else normalized_entry
    return title if title and not _looks_like_date_only(title) else None


def _extract_company(entry: str) -> str | None:
    normalized_entry = _strip_leading_date_range(entry)
    company_match = re.search(
        r"(?: at |[-–—|,]\s*)([A-Z][A-Za-z0-9 &.'-]{2,}?)(?=\s+(?:(?:19|20)\d{2})|[,|–—-]|$)",
        normalized_entry,
    )
    return company_match.group(1).strip() if company_match else None


def _extract_certification_name(entry: str) -> str | None:
    cleaned = _strip_leading_date_range(entry).strip(" -–—:|,\t")
    if not cleaned:
        return None
    cleaned = re.sub(
        r"\s+\b(?:issued by|issuer|provider)\b\s+.*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s+\b(?:19|20)\d{2}\b.*$", "", cleaned).strip(" -–—:|,\t")
    separator_match = re.match(r"(.+?)\s+(?:[-–—|])\s+", cleaned)
    if separator_match:
        cleaned = separator_match.group(1).strip(" -–—:|,\t")
    if not cleaned or re.fullmatch(
        r"(?:certifications?|certificates?|licenses?|licences?)",
        cleaned,
        flags=re.IGNORECASE,
    ):
        return None
    return cleaned


def _looks_like_date_only(value: str) -> bool:
    return bool(
        re.fullmatch(rf"{_date_token_pattern()}", value.strip(), flags=re.IGNORECASE)
    )


def _clean_profile_list_entries(entries: list[str]) -> list[str]:
    cleaned_items: list[str] = []
    for entry in entries:
        candidate_items = _split_list_items(entry)
        if not candidate_items:
            candidate_items = [entry.strip()]
        for item in candidate_items:
            cleaned = re.sub(r"^[-•*\s]+", "", item).strip(" -–—:\t")
            if cleaned and not re.fullmatch(
                r"(?:certifications?|languages?)", cleaned, flags=re.IGNORECASE
            ):
                cleaned_items.append(cleaned)
    return _deduplicate_preserving_order(cleaned_items)


def _split_list_items(text: str) -> list[str]:
    items: list[str] = []
    for part in re.split(r"[,;•\n]", text):
        item = part.strip(" -–—:\t")
        if 2 <= len(item) <= 60:
            items.append(item)
    return _deduplicate_preserving_order(items)


def _ordered_keyword_matches(text: str, keywords: tuple[str, ...]) -> list[str]:
    matches = [
        keyword
        for keyword in keywords
        if re.search(rf"\b{re.escape(keyword)}\b", text, flags=re.IGNORECASE)
    ]
    return _deduplicate_preserving_order(matches)


def _extract_labeled_date(text: str, labels: tuple[str, ...]) -> str | None:
    label_pattern = "|".join(re.escape(label) for label in labels)
    return _extract_first(
        rf"(?:{label_pattern})\s*[:\-]?\s*([A-Za-z]+\s+\d{{1,2}},?\s+\d{{4}}|\d{{1,2}}[./-]\d{{1,2}}[./-]\d{{2,4}}|\d{{4}}-\d{{2}}-\d{{2}})",
        text,
        capture_group=1,
    )


def _extract_money_for_label(text: str, labels: tuple[str, ...]) -> str | None:
    label_pattern = "|".join(re.escape(label) for label in labels)
    return _extract_first(
        rf"(?:{label_pattern})\s*[:\-]?\s*"
        r"((?:(?:CHF|USD|EUR|GBP|\$|€|£)\s*)?[0-9][0-9'.,]*)",
        text,
        capture_group=1,
    )


def _extract_money_components_for_label(
    text: str, labels: tuple[str, ...]
) -> tuple[float | None, str | None]:
    money = _extract_money_for_label(text, labels)
    if not money:
        return None, None
    currency = _currency_from_money(money)
    amount_text = re.sub(
        r"(?:CHF|USD|EUR|GBP|\$|€|£)", "", money, flags=re.IGNORECASE
    )
    normalized_amount = amount_text.replace("'", "").replace(" ", "")
    if "," in normalized_amount and "." in normalized_amount:
        normalized_amount = normalized_amount.replace(",", "")
    elif "," in normalized_amount:
        normalized_amount = normalized_amount.replace(",", ".")
    try:
        return round(float(normalized_amount), 2), currency
    except ValueError:
        return None, currency


def _currency_from_money(money: str) -> str | None:
    currency_match = re.search(r"CHF|USD|EUR|GBP|\$|€|£", money, flags=re.IGNORECASE)
    if not currency_match:
        return None
    symbol_or_code = currency_match.group(0).upper()
    return {"$": "USD", "€": "EUR", "£": "GBP"}.get(symbol_or_code, symbol_or_code)


def _extract_labeled_currency(text: str) -> str | None:
    explicit = _extract_first(
        r"currency\s*[:\-]\s*([A-Z]{3})", text, capture_group=1
    )
    if explicit:
        return explicit.upper()
    money_match = re.search(
        r"(?:CHF|USD|EUR|GBP|\$|€|£)", text, flags=re.IGNORECASE
    )
    return _currency_from_money(money_match.group(0)) if money_match else None


def _normalize_date(value: str | None) -> str | None:
    if not value:
        return None
    stripped = value.strip()
    iso_match = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", stripped)
    if iso_match:
        return stripped
    numeric_match = re.fullmatch(
        r"(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})", stripped
    )
    if numeric_match:
        day = int(numeric_match.group(1))
        month = int(numeric_match.group(2))
        year = int(numeric_match.group(3))
        if year < 100:
            year += 2000
        if day > 12 or month <= 12:
            return f"{year:04d}-{month:02d}-{day:02d}"
    month_match = re.fullmatch(
        r"([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})", stripped
    )
    if month_match:
        months = {
            name.lower(): index
            for index, name in enumerate(
                (
                    "January",
                    "February",
                    "March",
                    "April",
                    "May",
                    "June",
                    "July",
                    "August",
                    "September",
                    "October",
                    "November",
                    "December",
                ),
                start=1,
            )
        }
        month_text = month_match.group(1).lower()
        month = months.get(month_text) or months.get(f"{month_text[:3]}uary")
        short_months = {name[:3].lower(): index for name, index in months.items()}
        month = month or short_months.get(month_text[:3])
        if month:
            return f"{int(month_match.group(3)):04d}-{month:02d}-{int(month_match.group(2)):02d}"
    return stripped


def _extract_coverage_lines(text: str) -> list[str]:
    return _extract_labeled_lines(text, ("coverage", "covered", "benefit", "limit"))


def _extract_exclusion_lines(text: str) -> list[str]:
    return _extract_labeled_lines(text, ("exclusion", "excluded", "not covered"))


def _extract_labeled_lines(text: str, labels: tuple[str, ...]) -> list[str]:
    labeled_lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip(" •-*\t")
        if any(label in stripped.lower() for label in labels):
            labeled_lines.append(stripped)
    return _deduplicate_preserving_order(labeled_lines)[:20]


def _deduplicate_preserving_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    unique_items: list[str] = []
    for item in items:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        unique_items.append(item)
    return unique_items


def _without_empty_values(values: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value for key, value in values.items() if value not in (None, "", [], {})
    }


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
