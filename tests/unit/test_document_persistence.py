import asyncio

import pytest

from services import document_persistence
from services.document_persistence import (
    build_candidate_payload,
    build_insurance_payload,
    build_vector_db_metadata,
    build_vector_db_records,
    infer_pdf_domain,
    persist_document_if_supported,
    persist_extracted_payload,
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


def test_build_candidate_payload_normalizes_hyphenated_roles_and_inline_profile_sections() -> None:
    payload = build_candidate_payload(
        "Curriculum Vitae\n"
        "Mario Rossi\n"
        "Experience\n"
        "Software Engineer at Relewant – Chiasso\n"
        "2026.01 - present\n"
        "Developing an application that computes the derivative of functions.\n"
        "Full-stack Engineer at Purest Ltd – Lugano (Switzerland)\n"
        "2024.09 - 2024.12 Private Tutor in mathematics and physics\n"
        "Certifications: AWS Certified Cloud Practitioner - Amazon Web Services, 2025\n"
        "Languages: Italian - Native, English - B2"
    )

    assert payload["previous_works"] == [
        {
            "title": "Software Engineer",
            "company": "Relewant",
            "description": "Software Engineer at Relewant – Chiasso",
        },
        {
            "title": "Full-stack Engineer",
            "company": "Purest Ltd",
            "description": "Full-stack Engineer at Purest Ltd – Lugano (Switzerland)",
        },
        {
            "title": "Private Tutor in mathematics and physics",
            "date_range": "2024.09 - 2024.12",
            "description": "2024.09 - 2024.12 Private Tutor in mathematics and physics",
        },
    ]
    assert payload["certification"] == ["AWS Certified Cloud Practitioner"]
    assert payload["languages"] == ["Italian - Native", "English - B2"]


def test_build_insurance_payload_extracts_policy_fields() -> None:
    payload = build_insurance_payload(
        "Policy Number: POL-001\nProvider: Acme Insurance\nStatus: active\nHealth coverage"
    )

    assert payload["policy_number"] == "POL-001"
    assert payload["insurance_provider"] == "Acme Insurance"
    assert payload["insurance_type"] == "health"
    assert payload["currency"] == "EUR"
    assert payload["premium_amount"] == 0.0


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

    assert payload["insurance_provider"] == "Acme Insurance"
    assert payload["policy_holder"] == {"first_name": "Jane", "last_name": "Doe"}
    assert payload["start_date"] == "2026-01-01"
    assert payload["end_date"] == "2026-12-31"
    assert payload["premium_amount"] == 1200.0
    assert payload["currency"] == "CHF"
    assert payload["coverage_details"] == {
        "coverage_limit": 100000.0,
        "deductible": "CHF 500",
        "coverages": ["Coverage Limit: CHF 100'000", "Coverage: emergency health care"],
        "exclusions": ["Exclusion: pre-existing conditions"],
    }


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
    assert first_payload["policy_number"] == second_payload["policy_number"]


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


def test_build_vector_metadata_uses_extracted_insurance_payload_values() -> None:
    payload = {
        "id": "insurance-ai-1",
        "policy_number": "AI-POL-999",
        "insurance_type": "dental",
        "insurance_provider": "Payload Mutual",
        "policy_holder": {"first_name": "Amina", "last_name": "Policy"},
        "coverage_details": {"coverages": ["orthodontics"]},
        "premium_amount": 25.5,
        "raw_text": "Extracted policy text",
    }

    metadata = build_vector_db_metadata(payload, metadata_kind="insurance")

    assert metadata["policy_number"] == "AI-POL-999"
    assert metadata["insurance_type"] == "dental"
    assert metadata["insurance_provider"] == "Payload Mutual"
    assert metadata["policy_holder"] == {"first_name": "Amina", "last_name": "Policy"}
    assert metadata["coverage_details"] == {"coverages": ["orthodontics"]}
    assert metadata["premium_amount"] == 25.5


def test_build_vector_metadata_allows_missing_optional_insurance_fields() -> None:
    metadata = build_vector_db_metadata(
        {"id": "insurance-ai-2", "raw_text": "No optional values extracted"},
        metadata_kind="insurance",
    )

    assert metadata["policy_number"] is None
    assert metadata["insurance_type"] is None
    assert metadata["insurance_provider"] is None
    assert metadata["policy_holder"] is None
    assert metadata["coverage_details"] is None
    assert metadata["premium_amount"] is None
    assert metadata["currency"] == "EUR"


def test_build_vector_metadata_uses_extracted_candidate_payload_values() -> None:
    payload = {
        "id": "candidate-ai-1",
        "first_name": "Amina",
        "last_name": "Payload",
        "seniority": "principal",
        "competences": {"technical": ["rust", "python"]},
        "education": ["MSc Computer Science"],
        "certification": ["Kubernetes Administrator"],
        "languages": ["English", "French"],
        "raw_text": "Candidate profile",
    }

    metadata = build_vector_db_metadata(payload, metadata_kind="candidate")

    assert metadata["first_name"] == "Amina"
    assert metadata["last_name"] == "Payload"
    assert metadata["seniority"] == "principal"
    assert metadata["competences"] == {"technical": ["rust", "python"]}
    assert metadata["education"] == ["MSc Computer Science"]
    assert metadata["certification"] == ["Kubernetes Administrator"]
    assert metadata["languages"] == ["English", "French"]


def test_build_vector_metadata_allows_missing_optional_candidate_fields() -> None:
    metadata = build_vector_db_metadata(
        {"id": "candidate-ai-2", "raw_text": "No optional values extracted"},
        metadata_kind="candidate",
    )

    assert metadata["first_name"] is None
    assert metadata["last_name"] is None
    assert metadata["email"] is None
    assert metadata["phone"] is None
    assert metadata["seniority"] is None
    assert metadata["competences"] is None
    assert metadata["previous_works"] == []
    assert metadata["education"] == []
    assert metadata["certification"] == []
    assert metadata["languages"] == []


def test_build_vector_records_chunks_embedding_text_without_changing_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(document_persistence, "VECTOR_DB_CHUNK_SIZE", 5)
    records = build_vector_db_records(
        {
            "id": "candidate-ai-3",
            "first_name": "Chunky",
            "raw_text": "abcdefghijk",
        },
        metadata_kind="candidate",
    )

    assert len(records) == 3
    assert [record.payload["first_name"] for record in records] == [
        "Chunky",
        "Chunky",
        "Chunky",
    ]
    assert [record.payload["chunk_index"] for record in records] == [0, 1, 2]
    assert [record.payload["chunk_count"] for record in records] == [3, 3, 3]


def test_persist_extracted_payload_upserts_payload_metadata_without_semantic_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def fake_upsert_records(collection_name: str, records: list[object]) -> None:
        captured["collection_name"] = collection_name
        captured["payload"] = records[0].payload

    monkeypatch.setattr(document_persistence, "_upsert_records", fake_upsert_records)

    asyncio.run(
        persist_extracted_payload(
            "insurances",
            {
                "id": "insurance-ai-4",
                "insurance_type": "vision",
                "policy_number": "VIS-1",
                "raw_text": "Vision policy",
            },
            metadata_kind="insurance",
        )
    )

    assert captured["collection_name"] == "insurances"
    assert captured["payload"]["insurance_type"] == "vision"
    assert captured["payload"]["policy_number"] == "VIS-1"
    assert captured["payload"]["insurance_provider"] is None
    assert captured["payload"]["currency"] == "EUR"


def test_build_insurance_payload_maps_requested_insurance_schema_fields() -> None:
    payload = build_insurance_payload(
        "SafeLife Insurance\n"
        "Candidate ID: 123e4567-e89b-12d3-a456-426614174000\n"
        "Policy Number: LIFE-42\n"
        "Insurance Type: Life\n"
        "Policy Holder: John Doe\n"
        "Coverage Limit: 500000\n"
        "Medical: true\n"
        "Dental: false\n"
        "Accident: yes\n"
        "Start Date: 2026-02-01\n"
        "End Date: 2027-02-01\n"
        "Premium: 49.90\n"
        "Beneficiary: Jane Doe, Spouse"
    )

    assert payload["candidate_id"] == "123e4567-e89b-12d3-a456-426614174000"
    assert payload["policy_number"] == "LIFE-42"
    assert payload["insurance_provider"] == "SafeLife Insurance"
    assert payload["insurance_type"] == "life"
    assert payload["policy_holder"] == {"first_name": "John", "last_name": "Doe"}
    assert payload["coverage_details"]["coverage_limit"] == 500000.0
    assert payload["coverage_details"]["medical"] is True
    assert payload["coverage_details"]["dental"] is False
    assert payload["coverage_details"]["accident"] is True
    assert payload["start_date"] == "2026-02-01"
    assert payload["end_date"] == "2027-02-01"
    assert payload["premium_amount"] == 49.9
    assert payload["currency"] == "EUR"
    assert payload["beneficiary"] == {"name": "Jane Doe", "relationship": "Spouse"}


def test_build_vector_records_keeps_multipage_insurance_pdf_in_one_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(document_persistence, "VECTOR_DB_CHUNK_SIZE", 5)

    records = build_vector_db_records(
        build_insurance_payload(
            "Policy Number: MULTI-1\nProvider: Acme Insurance\n"
            "Premium: EUR 10.00\nCoverage Limit: EUR 1000"
        ),
        metadata_kind="insurance",
    )

    assert len(records) == 1
    assert records[0].payload["policy_number"] == "MULTI-1"
    assert "chunk_index" not in records[0].payload
