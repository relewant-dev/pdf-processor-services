import asyncio
import json

import pytest

from services import document_persistence
from services.document_persistence import (
    CandidateVectorMetadata,
    InsuranceVectorMetadata,
    VectorDbMetadataError,
    build_payload_with_ollama,
    build_vector_db_metadata,
    build_vector_db_records,
    infer_pdf_domain_with_ollama,
    persist_document_if_supported,
    persist_extracted_payload,
)


def test_removed_regex_metadata_builders_are_not_available() -> None:
    removed_names = (
        "infer_pdf_domain",
        "build_candidate_payload",
        "build_insurance_payload",
        "_extract_candidate_name",
        "_extract_candidate_education",
        "_extract_candidate_certifications",
        "_extract_candidate_previous_works",
        "_extract_candidate_competences",
        "_extract_insurance_provider_name",
        "_extract_insurance_coverage_details",
        "_detect_insurance_type",
    )

    for name in removed_names:
        assert not hasattr(document_persistence, name)


def test_build_metadata_extraction_prompt_contains_strict_schema_instructions() -> None:
    prompt = document_persistence._build_metadata_extraction_prompt(
        "Jane Doe\nEmail: jane@example.com",
        "candidate",
        CandidateVectorMetadata,
    )

    assert "You are an information extraction system." in prompt
    assert "Extract values only if explicitly supported by the document." in prompt
    assert "Do not infer or invent information." in prompt
    assert "Return only valid JSON." in prompt
    assert "Missing scalar values must be null. Missing arrays must be []." in prompt
    assert "Populate all fields defined in the schema." in prompt
    assert "The document may be written in any language." in prompt
    assert '"first_name"' in prompt
    assert '"previous_works"' in prompt
    assert "Jane Doe" in prompt


def test_infer_pdf_domain_with_ollama_uses_model_json_only() -> None:
    captured: dict[str, object] = {}

    async def fake_chat_with_ollama(prompt: str) -> str:
        captured["prompt"] = prompt
        return '{"document_type":"cv"}'

    original = document_persistence.chat_with_ollama
    document_persistence.chat_with_ollama = fake_chat_with_ollama
    try:
        domain = asyncio.run(
            infer_pdf_domain_with_ollama(
                "Work experience and education",
                "Summarize this CV",
            )
        )
    finally:
        document_persistence.chat_with_ollama = original

    assert domain == "cv"
    assert "Classify the uploaded document" in captured["prompt"]


def test_build_payload_with_ollama_uses_schema_format_and_service_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def fake_chat_with_ollama(
        prompt: str, *, response_format: dict[str, object] | str | None = None
    ) -> str:
        captured["prompt"] = prompt
        captured["response_format"] = response_format
        return json.dumps(
            {
                "id": None,
                "document_hash": None,
                "first_name": "Giulia",
                "last_name": "Bianchi",
                "email": "giulia@example.it",
                "phone": None,
                "seniority": None,
                "competences": None,
                "previous_works": [],
                "education": ["Laurea in Informatica"],
                "certification": [],
                "languages": ["Italiano"],
                "raw_text": None,
                "created_at": None,
                "updated_at": None,
            }
        )

    monkeypatch.setattr(document_persistence, "chat_with_ollama", fake_chat_with_ollama)

    payload = asyncio.run(
        build_payload_with_ollama(
            "Curriculum vitae\nGiulia Bianchi\nIstruzione: Laurea in Informatica",
            "candidate",
        )
    )

    assert payload["id"].startswith("candidate-")
    assert payload["document_hash"]
    assert payload["raw_text"] == (
        "Curriculum vitae\nGiulia Bianchi\nIstruzione: Laurea in Informatica"
    )
    assert payload["first_name"] == "Giulia"
    assert payload["education"] == ["Laurea in Informatica"]
    assert captured["response_format"] == CandidateVectorMetadata.model_json_schema()
    assert "JSON Schema" in captured["prompt"]


def test_build_payload_with_ollama_uses_insurance_schema_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def fake_chat_with_ollama(
        prompt: str, *, response_format: dict[str, object] | str | None = None
    ) -> str:
        captured["prompt"] = prompt
        captured["response_format"] = response_format
        return json.dumps(
            {
                "id": None,
                "document_hash": None,
                "candidate_id": None,
                "policy_number": "ITA-001",
                "insurance_provider": "Assicurazioni Acme",
                "insurance_type": "salute",
                "policy_holder": None,
                "coverage_details": {"coverages": ["Spese mediche"]},
                "start_date": "2026-01-01",
                "end_date": None,
                "premium_amount": None,
                "currency": "EUR",
                "beneficiary": None,
                "raw_text": None,
                "created_at": None,
                "updated_at": None,
            }
        )

    monkeypatch.setattr(document_persistence, "chat_with_ollama", fake_chat_with_ollama)

    payload = asyncio.run(
        build_payload_with_ollama(
            "Polizza numero ITA-001\nCompagnia Assicurazioni Acme",
            "insurance",
        )
    )

    assert payload["policy_number"] == "ITA-001"
    assert payload["insurance_provider"] == "Assicurazioni Acme"
    assert payload["id"]
    assert captured["response_format"] == InsuranceVectorMetadata.model_json_schema()
    assert "policy_number" in captured["prompt"]


def test_parse_json_object_rejects_non_json_wrappers() -> None:
    with pytest.raises(VectorDbMetadataError):
        document_persistence._parse_json_object('Here is JSON: {"document_type":"cv"}')


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


def test_persist_document_if_supported_upserts_cv_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}
    model_responses = iter(
        [
            '{"document_type":"cv"}',
            json.dumps(
                {
                    "id": None,
                    "document_hash": None,
                    "first_name": "Giulia",
                    "last_name": "Bianchi",
                    "email": "giulia@example.it",
                    "phone": None,
                    "seniority": None,
                    "competences": None,
                    "previous_works": [],
                    "education": ["Laurea in Informatica"],
                    "certification": [],
                    "languages": ["Italiano"],
                    "raw_text": None,
                    "created_at": None,
                    "updated_at": None,
                }
            ),
        ]
    )

    async def fake_chat_with_ollama(
        prompt: str, *, response_format: dict[str, object] | str | None = None
    ) -> str:
        calls.setdefault("prompts", []).append(prompt)
        calls.setdefault("formats", []).append(response_format)
        return next(model_responses)

    async def fake_upsert_payload(
        collection_name: str, payload: dict[str, object]
    ) -> None:
        calls["upsert_collection"] = collection_name
        calls["upsert_hash"] = payload["document_hash"]
        calls["upsert_raw_text"] = payload["raw_text"]
        calls["upsert_first_name"] = payload["first_name"]
        calls["upsert_education"] = payload["education"]

    monkeypatch.setattr(document_persistence, "chat_with_ollama", fake_chat_with_ollama)
    monkeypatch.setattr(document_persistence, "_upsert_payload", fake_upsert_payload)

    domain = asyncio.run(
        persist_document_if_supported(
            "Curriculum vitae\nGiulia Bianchi\nIstruzione: Laurea in Informatica",
            "Leggi questo CV",
        )
    )

    assert domain == "cv"
    assert calls["upsert_collection"] == document_persistence.QDRANT_CANDIDATES_COLLECTION
    assert "upsert_hash" in calls
    assert calls["upsert_raw_text"] == (
        "Curriculum vitae\nGiulia Bianchi\nIstruzione: Laurea in Informatica"
    )
    assert calls["upsert_first_name"] == "Giulia"
    assert calls["upsert_education"] == ["Laurea in Informatica"]
    assert "first_name" in calls["prompts"][1]
    assert calls["formats"][1] == CandidateVectorMetadata.model_json_schema()


def test_persist_document_if_supported_saves_new_insurance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}
    model_responses = iter(
        [
            '{"document_type":"insurance"}',
            json.dumps(
                {
                    "id": None,
                    "document_hash": None,
                    "candidate_id": None,
                    "policy_number": "ITA-001",
                    "insurance_provider": "Assicurazioni Acme",
                    "insurance_type": None,
                    "policy_holder": None,
                    "coverage_details": None,
                    "start_date": "2026-01-01",
                    "end_date": None,
                    "premium_amount": None,
                    "currency": "EUR",
                    "beneficiary": None,
                    "raw_text": None,
                    "created_at": None,
                    "updated_at": None,
                }
            ),
        ]
    )

    async def fake_chat_with_ollama(
        prompt: str, *, response_format: dict[str, object] | str | None = None
    ) -> str:
        calls.setdefault("prompts", []).append(prompt)
        calls.setdefault("formats", []).append(response_format)
        return next(model_responses)

    async def fake_upsert_payload(
        collection_name: str, payload: dict[str, object]
    ) -> None:
        calls["upsert_collection"] = collection_name
        calls["upsert_hash"] = payload["document_hash"]
        calls["upsert_policy_number"] = payload["policy_number"]
        calls["upsert_start_date"] = payload["start_date"]

    monkeypatch.setattr(document_persistence, "chat_with_ollama", fake_chat_with_ollama)
    monkeypatch.setattr(document_persistence, "_upsert_payload", fake_upsert_payload)

    domain = asyncio.run(
        persist_document_if_supported(
            "Polizza numero: ITA-001\nCompagnia: Assicurazioni Acme\nDecorrenza: 01/01/2026",
            "Spiega la copertura assicurativa",
        )
    )

    assert domain == "insurance"
    assert calls["upsert_collection"] == document_persistence.QDRANT_INSURANCES_COLLECTION
    assert "upsert_hash" in calls
    assert calls["upsert_policy_number"] == "ITA-001"
    assert calls["upsert_start_date"] == "2026-01-01"
    assert "start_date" in calls["prompts"][1]
    assert calls["formats"][1] == InsuranceVectorMetadata.model_json_schema()


def test_build_vector_records_keeps_multipage_insurance_pdf_in_one_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(document_persistence, "VECTOR_DB_CHUNK_SIZE", 5)

    records = build_vector_db_records(
        {
            "id": "insurance-ai-5",
            "policy_number": "MULTI-1",
            "insurance_provider": "Acme Insurance",
            "raw_text": "Policy Number: MULTI-1\nProvider: Acme Insurance\fPremium EUR 10.00",
        },
        ),
        metadata_kind="insurance",
    )

    assert len(records) == 1
    assert records[0].payload["policy_number"] == "MULTI-1"
    assert "chunk_index" not in records[0].payload
