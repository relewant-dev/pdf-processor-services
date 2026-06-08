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


def test_build_insurance_payload_extracts_policy_fields() -> None:
    payload = build_insurance_payload(
        "Policy Number: POL-001\nProvider: Acme Insurance\nStatus: active\nHealth coverage"
    )

    assert payload["insurance_number"] == "POL-001"
    assert payload["provider_name"] == "Acme Insurance"
    assert payload["status"] == "active"
    assert payload["insurance_type"] == "health"


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


def test_persist_document_if_supported_skips_existing_cv(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    async def fake_document_exists(
        collection_name: str, payload: dict[str, object]
    ) -> bool:
        calls["exists_collection"] = collection_name
        calls["exists_hash"] = payload["document_hash"]
        calls["exists_raw_text"] = payload["raw_text"]
        return True

    async def fake_upsert_payload(
        collection_name: str, payload: dict[str, object]
    ) -> None:
        calls["upsert_collection"] = collection_name

    monkeypatch.setattr(document_persistence, "_document_exists", fake_document_exists)
    monkeypatch.setattr(document_persistence, "_upsert_payload", fake_upsert_payload)

    domain = asyncio.run(
        persist_document_if_supported(
            "Jane Doe\nEmail: jane@example.com\nWork experience",
            "Read this CV",
        )
    )

    assert domain == "cv"
    assert (
        calls["exists_collection"] == document_persistence.QDRANT_CANDIDATES_COLLECTION
    )
    assert "exists_hash" in calls
    assert "upsert_collection" not in calls


def test_persist_document_if_supported_saves_new_insurance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    async def fake_document_exists(
        collection_name: str, payload: dict[str, object]
    ) -> bool:
        calls["exists_collection"] = collection_name
        calls["exists_hash"] = payload["document_hash"]
        calls["exists_raw_text"] = payload["raw_text"]
        return False

    async def fake_upsert_payload(
        collection_name: str, payload: dict[str, object]
    ) -> None:
        calls["upsert_collection"] = collection_name
        calls["upsert_hash"] = payload["document_hash"]

    monkeypatch.setattr(document_persistence, "_document_exists", fake_document_exists)
    monkeypatch.setattr(document_persistence, "_upsert_payload", fake_upsert_payload)

    domain = asyncio.run(
        persist_document_if_supported(
            "Policy Number: POL-001\nProvider: Acme Insurance\nStatus: active",
            "Explain insurance coverage",
        )
    )

    assert domain == "insurance"
    assert (
        calls["exists_collection"] == document_persistence.QDRANT_INSURANCES_COLLECTION
    )
    assert (
        calls["upsert_collection"] == document_persistence.QDRANT_INSURANCES_COLLECTION
    )
    assert calls["upsert_hash"] == calls["exists_hash"]


def test_build_metadata_extraction_prompt_uses_compact_contract() -> None:
    prompt = document_persistence._build_metadata_extraction_prompt(
        "Jane Doe\nSenior Python engineer",
        "candidate",
    )

    assert "JSON Schema" not in prompt
    assert "model_json_schema" not in prompt
    assert "first_name" in prompt
    assert "certifications" in prompt
    assert "Return only valid JSON" in prompt


def test_normalize_extracted_candidate_payload_fills_missing_optional_fields() -> None:
    normalized = document_persistence._normalize_extracted_payload(
        {"first_name": "Jane", "last_name": "Doe", "competences": ["Python"]},
        "candidate",
    )
    validated = document_persistence.build_vector_db_metadata(normalized, "candidate")

    assert validated["first_name"] == "Jane"
    assert validated["email"] is None
    assert validated["previous_works"] == []
    assert validated["education"] == []
    assert validated["certifications"] == []
    assert validated["competences"] == ["Python"]


def test_normalize_extracted_payload_preserves_service_metadata() -> None:
    normalized = document_persistence._normalize_extracted_payload(
        {
            "id": "candidate-existing",
            "document_hash": "abc123",
            "raw_text": "raw",
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-02T00:00:00+00:00",
        },
        "candidate",
    )

    assert normalized["id"] == "candidate-existing"
    assert normalized["document_hash"] == "abc123"
    assert normalized["raw_text"] == "raw"
    assert normalized["created_at"] == "2026-01-01T00:00:00+00:00"
    assert normalized["updated_at"] == "2026-01-02T00:00:00+00:00"


def test_with_service_metadata_adds_document_identity() -> None:
    payload = document_persistence._with_service_metadata(
        {"first_name": "Jane"},
        "candidate",
        "Jane Doe\nSenior engineer",
    )

    assert payload["id"].startswith("candidate-")
    assert payload["document_hash"]
    assert payload["raw_text"] == "Jane Doe\nSenior engineer"
    assert payload["created_at"]
    assert payload["updated_at"]
    assert payload["first_name"] == "Jane"


def test_extract_payload_with_ollama_uses_json_response_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def fake_chat_with_ollama(
        prompt: str, response_format: object = None
    ) -> str:
        captured["prompt"] = prompt
        captured["response_format"] = response_format
        return '{"first_name":"Jane","last_name":"Doe"}'

    monkeypatch.setattr(
        document_persistence, "chat_with_ollama", fake_chat_with_ollama
    )

    payload = asyncio.run(
        document_persistence.extract_payload_with_ollama(
            "Jane Doe\nSenior engineer",
            "candidate",
        )
    )

    assert captured["response_format"] == "json"
    assert "JSON Schema" not in captured["prompt"]
    assert payload["first_name"] == "Jane"
    assert payload["email"] is None
