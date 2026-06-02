from __future__ import annotations

import hashlib
import re
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
    provider_name = _extract_insurance_provider_name(document_text)

    return {
        "id": f"insurance-{document_hash}",
        "document_hash": document_hash,
        "insurance_number": policy_number or f"unknown-{document_hash[:12]}",
        "insurance_type": _detect_insurance_type(document_text),
        "provider_name": provider_name,
        "status": _detect_insurance_status(document_text),
        "coverage_details": _extract_insurance_coverage_details(document_text),
        "documents": _extract_insurance_document_references(document_text),
        "raw_text": document_text,
        "created_at": _utc_timestamp(),
        "updated_at": _utc_timestamp(),
    }


async def persist_document_if_supported(document_text: str, question: str) -> str:
    domain = infer_pdf_domain(document_text, question)
    if domain == "cv":
        payload = build_candidate_payload(document_text)
        await _upsert_payload(QDRANT_CANDIDATES_COLLECTION, payload)
    elif domain == "insurance":
        payload = build_insurance_payload(document_text)
        await _upsert_payload(QDRANT_INSURANCES_COLLECTION, payload)
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


def _extract_insurance_coverage_details(text: str) -> dict[str, Any]:
    details = _without_empty_values(
        {
            "policyholder": _extract_first(
                r"(?:policyholder|insured|member|name)\s*[:\-]\s*([^\n]+)",
                text,
                capture_group=1,
            ),
            "effective_date": _extract_labeled_date(
                text, ("effective date", "start date", "valid from")
            ),
            "expiration_date": _extract_labeled_date(
                text, ("expiration date", "expiry date", "end date", "valid until")
            ),
            "premium": _extract_money_for_label(text, ("premium", "amount due")),
            "deductible": _extract_money_for_label(text, ("deductible", "excess")),
            "coverage_limit": _extract_money_for_label(
                text, ("coverage limit", "limit", "sum insured")
            ),
            "beneficiary": _extract_first(
                r"beneficiary\s*[:\-]\s*([^\n]+)", text, capture_group=1
            ),
        }
    )
    coverages = _extract_coverage_lines(text)
    exclusions = _extract_exclusion_lines(text)
    if coverages:
        details["coverages"] = coverages
    if exclusions:
        details["exclusions"] = exclusions
    return details


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
        rf"(?:{label_pattern})\s*[:\-]?\s*((?:CHF|USD|EUR|GBP|\$|€|£)\s?[0-9][0-9'.,]*)",
        text,
        capture_group=1,
    )


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
