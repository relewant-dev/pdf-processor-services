import asyncio

import pytest

from services import document_persistence
from services.document_persistence import (
    build_candidate_payload,
    build_insurance_payload,
    infer_pdf_domain,
    persist_document_if_supported,
)


def test_infer_pdf_domain_detects_cv() -> None:
    assert (
        infer_pdf_domain("Work experience and education", "Summarize this CV") == "cv"
    )


def test_infer_pdf_domain_detects_insurance() -> None:
    assert (
        infer_pdf_domain("Policy number 123", "Explain insurance coverage")
        == "insurance"
    )


def test_infer_pdf_domain_returns_other_for_unsupported_documents() -> None:
    assert (
        infer_pdf_domain("Quarterly revenue and EBITDA", "Summarize this report")
        == "other"
    )


def test_build_candidate_payload_extracts_contact_fields() -> None:
    payload = build_candidate_payload(
        "Jane Doe\nEmail: jane@example.com\nPhone: +1 202 555 0110\nSenior engineer"
    )

    assert payload["first_name"] == "Jane"
    assert payload["last_name"] == "Doe"
    assert payload["email"] == "jane@example.com"
    assert payload["seniority"] == "senior"


def test_build_candidate_payload_maps_cv_sections_to_structured_fields() -> None:
    payload = build_candidate_payload(
        "Curriculum Vitae\n"
        "Jane Doe\n"
        "Email: jane@example.com\n"
        "Experience\n"
        "Software Engineer - Acme Labs 2021 - Present\n"
        "Built Python services and React dashboards.\n"
        "Education\n"
        "Master of Science in Artificial Intelligence - Università della Svizzera italiana, 2020 - 2022\n"
        "Skills\n"
        "Python, React, SQL, Docker"
    )

    assert payload["first_name"] == "Jane"
    assert payload["last_name"] == "Doe"
    assert payload["previous_works"] == [
        {
            "title": "Software Engineer",
            "company": "Acme Labs",
            "date_range": "2021 - Present",
            "description": "Software Engineer - Acme Labs 2021 - Present Built Python services and React dashboards.",
        }
    ]
    assert payload["education"] == ["Master of Science in Artificial Intelligence"]
    assert payload["certification"] == []
    assert payload["languages"] == []
    assert payload["competences"]["technical"] == ["python", "react", "sql", "docker"]


def test_build_candidate_payload_extracts_profile_lists_and_ignores_personal_dates() -> (
    None
):
    payload = build_candidate_payload(
        "Curriculum Vitae\n"
        "Mario Rossi\n"
        "Experience\n"
        "2024.09–2024.12 Private Tutor in mathematics and physics\n"
        "2022.09–present\n"
        "Date of Birth: 18.02.2002 Place of Birth: Varese, Comerio\n"
        "Education\n"
        "Bachelor Degree in Mathematics - University of Milan, 2020 - 2023\n"
        "Master of Science in Data Science - Politecnico di Milano, 2023 - 2025\n"
        "Certifications\n"
        "AWS Certified Cloud Practitioner\n"
        "First Certificate in English\n"
        "Languages\n"
        "Italian - Native\n"
        "English - B2"
    )

    assert payload["previous_works"] == [
        {
            "title": "Private Tutor in mathematics and physics",
            "date_range": "2024.09 - 2024.12",
            "description": "2024.09–2024.12 Private Tutor in mathematics and physics",
        }
    ]
    assert payload["education"] == [
        "Bachelor Degree in Mathematics",
        "Master of Science in Data Science",
    ]
    assert payload["certification"] == [
        "AWS Certified Cloud Practitioner",
        "First Certificate in English",
    ]
    assert payload["languages"] == ["Italian - Native", "English - B2"]


def test_build_insurance_payload_extracts_policy_fields() -> None:
    payload = build_insurance_payload(
        "Policy Number: POL-001\nProvider: Acme Insurance\nStatus: active\nHealth coverage"
    )

    assert payload["insurance_number"] == "POL-001"
    assert payload["provider_name"] == "Acme Insurance"
    assert payload["status"] == "active"
    assert payload["insurance_type"] == "health"


def test_build_insurance_payload_maps_policy_fields_to_coverage_details() -> None:
    payload = build_insurance_payload(
        "Acme Insurance\n"
        "Policy Number: POL-001\n"
        "Policyholder: Jane Doe\n"
        "Effective Date: 01/01/2026\n"
        "Expiration Date: 31/12/2026\n"
        "Premium: CHF 1'200.00\n"
        "Deductible: CHF 500\n"
        "Coverage Limit: CHF 100'000\n"
        "Coverage: emergency health care\n"
        "Exclusion: pre-existing conditions\n"
        "Endorsement No. END-42"
    )

    assert payload["provider_name"] == "Acme Insurance"
    assert payload["coverage_details"] == {
        "policyholder": "Jane Doe",
        "effective_date": "01/01/2026",
        "expiration_date": "31/12/2026",
        "premium": "CHF 1'200.00",
        "deductible": "CHF 500",
        "coverage_limit": "CHF 100'000",
        "coverages": ["Coverage Limit: CHF 100'000", "Coverage: emergency health care"],
        "exclusions": ["Exclusion: pre-existing conditions"],
    }
    assert payload["documents"] == [{"type": "endorsement", "reference": "END-42"}]


def test_build_candidate_payload_uses_stable_document_identity() -> None:
    first_payload = build_candidate_payload(
        "Jane Doe\nEmail: jane@example.com\nSenior engineer"
    )
    second_payload = build_candidate_payload(
        " Jane Doe \n\n Email: jane@example.com \n Senior engineer "
    )

    assert first_payload["document_hash"] == second_payload["document_hash"]
    assert first_payload["id"] == second_payload["id"]


def test_build_insurance_payload_uses_stable_unknown_policy_number() -> None:
    first_payload = build_insurance_payload("Provider: Acme Insurance\nHealth coverage")
    second_payload = build_insurance_payload(
        " Provider: Acme Insurance \n Health coverage "
    )

    assert first_payload["document_hash"] == second_payload["document_hash"]
    assert first_payload["insurance_number"] == second_payload["insurance_number"]


def test_persist_document_if_supported_upserts_cv_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    async def fake_upsert_payload(
        collection_name: str, payload: dict[str, object]
    ) -> None:
        calls["upsert_collection"] = collection_name
        calls["upsert_hash"] = payload["document_hash"]
        calls["upsert_raw_text"] = payload["raw_text"]

    monkeypatch.setattr(document_persistence, "_upsert_payload", fake_upsert_payload)

    domain = asyncio.run(
        persist_document_if_supported(
            "Jane Doe\nEmail: jane@example.com\nWork experience",
            "Read this CV",
        )
    )

    assert domain == "cv"
    assert (
        calls["upsert_collection"] == document_persistence.QDRANT_CANDIDATES_COLLECTION
    )
    assert "upsert_hash" in calls
    assert (
        calls["upsert_raw_text"] == "Jane Doe\nEmail: jane@example.com\nWork experience"
    )


def test_persist_document_if_supported_saves_new_insurance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    async def fake_upsert_payload(
        collection_name: str, payload: dict[str, object]
    ) -> None:
        calls["upsert_collection"] = collection_name
        calls["upsert_hash"] = payload["document_hash"]

    monkeypatch.setattr(document_persistence, "_upsert_payload", fake_upsert_payload)

    domain = asyncio.run(
        persist_document_if_supported(
            "Policy Number: POL-001\nProvider: Acme Insurance\nStatus: active",
            "Explain insurance coverage",
        )
    )

    assert domain == "insurance"
    assert (
        calls["upsert_collection"] == document_persistence.QDRANT_INSURANCES_COLLECTION
    )
    assert "upsert_hash" in calls
