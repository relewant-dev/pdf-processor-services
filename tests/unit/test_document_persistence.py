import asyncio
import json

import pytest
from fastmcp.exceptions import ToolError

from services import document_persistence
from services.document_persistence import (
    CandidateVectorMetadata,
    InsuranceVectorMetadata,
    VectorDbMetadataError,
    answer_document_prompt_from_database,
    build_vector_db_metadata,
    build_vector_db_records,
    extract_payload_with_ollama,
    infer_pdf_domain_with_ollama,
    persist_extracted_payload,
)


def test_legacy_duplicate_processing_functions_are_not_available() -> None:
    removed_names = (
        "persist_document_if_supported",
        "build_payload_with_ollama",
        "build_document_prompt",
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


def test_candidate_schema_contains_required_table_fields() -> None:
    schema_fields = set(CandidateVectorMetadata.model_fields)

    assert {
        "id",
        "first_name",
        "last_name",
        "email",
        "phone",
        "seniority",
        "city",
        "country",
        "address",
        "competences",
        "previous_works",
        "education",
        "current_job_title",
        "current_company",
        "availability_date",
        "notes",
        "language",
        "certifications",
        "created_at",
        "updated_at",
    }.issubset(schema_fields)


def test_insurance_schema_contains_required_table_fields() -> None:
    schema_fields = set(InsuranceVectorMetadata.model_fields)

    assert {
        "id",
        "candidate_id",
        "policy_number",
        "insurance_provider",
        "insurance_type",
        "policy_holder",
        "coverage_details",
        "start_date",
        "end_date",
        "premium_amount",
        "currency",
        "beneficiary",
        "created_at",
        "updated_at",
    }.issubset(schema_fields)


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
    assert '"language"' in prompt
    assert '"certifications"' in prompt
    assert "Jane Doe" in prompt


def test_infer_pdf_domain_with_ollama_uses_model_json_only(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    async def fake_chat_with_ollama(
        prompt: str, *, response_format: dict[str, object] | str | None = None
    ) -> str:
        captured["prompt"] = prompt
        captured["response_format"] = response_format
        return '{"document_type":"cv"}'

    monkeypatch.setattr(document_persistence, "chat_with_ollama", fake_chat_with_ollama)

    domain = asyncio.run(
        infer_pdf_domain_with_ollama(
            "Work experience and education",
            "Summarize this CV",
        )
    )

    assert domain == "cv"
    assert (
        captured["response_format"]
        == document_persistence._domain_classification_schema()
    )
    assert "Classify the uploaded document" in captured["prompt"]
    assert "Do not answer the user question" in captured["prompt"]


def test_extract_payload_with_ollama_uses_candidate_schema_format_and_service_metadata(
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
                "first_name": "Giulia",
                "last_name": "Bianchi",
                "email": "giulia@example.it",
                "phone": None,
                "seniority": None,
                "city": "Roma",
                "country": "Italia",
                "address": None,
                "competences": None,
                "previous_works": [],
                "education": [{"degree": "Laurea in Informatica"}],
                "current_job_title": "Engineer",
                "current_company": "Acme",
                "availability_date": None,
                "notes": None,
                "language": ["Italiano"],
                "certifications": [],
                "created_at": None,
                "updated_at": None,
            }
        )

    monkeypatch.setattr(document_persistence, "chat_with_ollama", fake_chat_with_ollama)

    payload = asyncio.run(
        extract_payload_with_ollama(
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
    assert payload["education"] == [{"degree": "Laurea in Informatica"}]
    assert captured["response_format"] == CandidateVectorMetadata.model_json_schema()
    assert "JSON Schema" in captured["prompt"]


def test_extract_payload_with_ollama_uses_insurance_schema_format(
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
                "created_at": None,
                "updated_at": None,
            }
        )

    monkeypatch.setattr(document_persistence, "chat_with_ollama", fake_chat_with_ollama)

    payload = asyncio.run(
        extract_payload_with_ollama(
            "Polizza numero ITA-001\nCompagnia Assicurazioni Acme",
            "insurance",
        )
    )

    assert payload["policy_number"] == "ITA-001"
    assert payload["insurance_provider"] == "Assicurazioni Acme"
    assert payload["id"]
    assert captured["response_format"] == InsuranceVectorMetadata.model_json_schema()
    assert "policy_number" in captured["prompt"]


def test_parse_json_object_accepts_embedded_json_wrappers() -> None:
    assert document_persistence._parse_json_object(
        'Here is JSON: {"document_type":"cv"}'
    ) == {"document_type": "cv"}


def test_parse_json_object_rejects_empty_response() -> None:
    with pytest.raises(VectorDbMetadataError, match="empty metadata response"):
        document_persistence._parse_json_object("  ")


def test_build_vector_metadata_uses_extracted_insurance_payload_values() -> None:
    payload = {
        "id": "insurance-ai-1",
        "policy_number": "AI-POL-999",
        "insurance_type": "dental",
        "insurance_provider": "Payload Mutual",
        "policy_holder": {"first_name": "Amina", "last_name": "Policy"},
        "coverage_details": {"coverages": ["orthodontics"]},
        "premium_amount": 25.5,
        "currency": "EUR",
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
        "city": "Paris",
        "country": "France",
        "competences": {"technical": ["rust", "python"]},
        "education": [{"degree": "MSc Computer Science"}],
        "certifications": ["Kubernetes Administrator"],
        "language": ["English", "French"],
        "current_job_title": "Principal Engineer",
        "current_company": "Acme",
        "raw_text": "Candidate profile",
    }

    metadata = build_vector_db_metadata(payload, metadata_kind="candidate")

    assert metadata["first_name"] == "Amina"
    assert metadata["last_name"] == "Payload"
    assert metadata["seniority"] == "principal"
    assert metadata["city"] == "Paris"
    assert metadata["country"] == "France"
    assert metadata["competences"] == {"technical": ["rust", "python"]}
    assert metadata["education"] == [{"degree": "MSc Computer Science"}]
    assert metadata["certifications"] == ["Kubernetes Administrator"]
    assert metadata["language"] == ["English", "French"]


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
    assert metadata["city"] is None
    assert metadata["country"] is None
    assert metadata["address"] is None
    assert metadata["competences"] is None
    assert metadata["previous_works"] == []
    assert metadata["education"] == []
    assert metadata["current_job_title"] is None
    assert metadata["current_company"] is None
    assert metadata["availability_date"] is None
    assert metadata["notes"] is None
    assert metadata["language"] is None
    assert metadata["certifications"] == []


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


def test_database_first_workflow_uses_existing_candidate_without_extraction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {"extract_count": 0}
    existing_record = {
        "id": "candidate-existing",
        "document_hash": document_persistence._document_hash("CV text"),
        "raw_text": "CV text",
        "first_name": "Ada",
        "last_name": "Lovelace",
        "certifications": ["Math"],
        "language": ["English"],
    }

    async def fake_infer(document_text: str, question: str) -> str:
        raise AssertionError("existing records should not be classified again")

    async def fake_get_document_by_hash(collection_name: str, document_hash: str):
        calls["collection"] = collection_name
        calls["hash"] = document_hash
        return existing_record

    async def fake_extract(document_text: str, metadata_kind: str) -> dict[str, object]:
        calls["extract_count"] = int(calls["extract_count"]) + 1
        return {}

    async def fake_chat_with_ollama(
        prompt: str, *, response_format: dict[str, object] | str | None = None
    ) -> str:
        calls["answer_prompt"] = prompt
        return "Ada is stored in the database."

    monkeypatch.setattr(document_persistence, "infer_pdf_domain_with_ollama", fake_infer)
    monkeypatch.setattr(
        document_persistence, "get_document_by_hash", fake_get_document_by_hash
    )
    monkeypatch.setattr(document_persistence, "extract_payload_with_ollama", fake_extract)
    monkeypatch.setattr(document_persistence, "chat_with_ollama", fake_chat_with_ollama)
    monkeypatch.setattr(
        document_persistence,
        "log_performance_event",
        lambda event, **fields: calls.update(
            {"performance_event": event, "performance_fields": fields}
        ),
    )

    result = asyncio.run(answer_document_prompt_from_database("CV text", "Who is this?"))

    assert result.response == "Ada is stored in the database."
    assert result.record_existed is True
    assert calls["collection"] == document_persistence.QDRANT_CANDIDATES_COLLECTION
    assert calls["extract_count"] == 0
    assert "raw_text" not in calls["answer_prompt"]
    assert "CV text" not in calls["answer_prompt"]
    assert "Ada" in calls["answer_prompt"]
    assert calls["performance_event"] == "document_database_workflow_completed"
    performance_fields = calls["performance_fields"]
    assert performance_fields["document_type"] == "cv"
    assert performance_fields["collection_name"] == document_persistence.QDRANT_CANDIDATES_COLLECTION
    assert performance_fields["record_existed"] is True
    assert "initial_lookup_duration_ms" in performance_fields
    assert "answer_duration_ms" in performance_fields


def test_database_first_workflow_extracts_saves_retrieves_then_answers_new_insurance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {"get_count": 0, "upsert_count": 0}
    saved_record = {
        "id": "insurance-saved",
        "document_hash": document_persistence._document_hash("Policy text"),
        "raw_text": "Policy text",
        "policy_number": "POL-1",
        "insurance_provider": "Acme",
    }

    async def fake_infer(document_text: str, question: str) -> str:
        return "insurance"

    async def fake_get_document_by_hash(collection_name: str, document_hash: str):
        calls["get_count"] = int(calls["get_count"]) + 1
        if calls["get_count"] < 3:
            return None
        return saved_record

    async def fake_extract(document_text: str, metadata_kind: str) -> dict[str, object]:
        calls["extract_kind"] = metadata_kind
        return saved_record

    async def fake_upsert_payload(collection_name: str, payload: dict[str, object]) -> None:
        calls["upsert_count"] = int(calls["upsert_count"]) + 1
        calls["upsert_collection"] = collection_name
        calls["upsert_payload"] = payload

    async def fake_chat_with_ollama(
        prompt: str, *, response_format: dict[str, object] | str | None = None
    ) -> str:
        calls["answer_prompt"] = prompt
        return "Policy POL-1 is stored."

    monkeypatch.setattr(document_persistence, "infer_pdf_domain_with_ollama", fake_infer)
    monkeypatch.setattr(
        document_persistence, "get_document_by_hash", fake_get_document_by_hash
    )
    monkeypatch.setattr(document_persistence, "extract_payload_with_ollama", fake_extract)
    monkeypatch.setattr(document_persistence, "_upsert_payload", fake_upsert_payload)
    monkeypatch.setattr(document_persistence, "chat_with_ollama", fake_chat_with_ollama)
    monkeypatch.setattr(
        document_persistence,
        "log_performance_event",
        lambda event, **fields: calls.update(
            {"performance_event": event, "performance_fields": fields}
        ),
    )

    result = asyncio.run(answer_document_prompt_from_database("Policy text", "Summarize"))

    assert result.response == "Policy POL-1 is stored."
    assert result.record_existed is False
    assert calls["get_count"] == 3
    assert calls["upsert_count"] == 1
    assert calls["extract_kind"] == "insurance"
    assert calls["upsert_collection"] == document_persistence.QDRANT_INSURANCES_COLLECTION
    assert "raw_text" not in calls["answer_prompt"]
    assert "Policy text" not in calls["answer_prompt"]
    assert "POL-1" in calls["answer_prompt"]
    assert calls["performance_event"] == "document_database_workflow_completed"
    performance_fields = calls["performance_fields"]
    assert performance_fields["document_type"] == "insurance"
    assert performance_fields["collection_name"] == document_persistence.QDRANT_INSURANCES_COLLECTION
    assert performance_fields["record_existed"] is False
    assert "metadata_extraction_duration_ms" in performance_fields
    assert "upsert_duration_ms" in performance_fields
    assert "saved_record_lookup_duration_ms" in performance_fields


def test_database_first_workflow_rejects_other_documents(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_infer(document_text: str, question: str) -> str:
        return "other"

    async def fake_get_document_by_hash(collection_name: str, document_hash: str):
        return None

    monkeypatch.setattr(document_persistence, "infer_pdf_domain_with_ollama", fake_infer)
    monkeypatch.setattr(
        document_persistence, "get_document_by_hash", fake_get_document_by_hash
    )

    with pytest.raises(ToolError, match="CV or an insurance"):
        asyncio.run(answer_document_prompt_from_database("Invoice text", "Summarize"))


def test_database_first_workflow_converts_metadata_errors_to_tool_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_infer(document_text: str, question: str) -> str:
        raise VectorDbMetadataError("Ollama returned an empty metadata response.")

    async def fake_get_document_by_hash(collection_name: str, document_hash: str):
        return None

    monkeypatch.setattr(document_persistence, "infer_pdf_domain_with_ollama", fake_infer)
    monkeypatch.setattr(
        document_persistence, "get_document_by_hash", fake_get_document_by_hash
    )

    with pytest.raises(ToolError, match="Unable to process PDF metadata"):
        asyncio.run(answer_document_prompt_from_database("CV text", "Summarize"))


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
        metadata_kind="insurance",
    )

    assert len(records) == 1
    assert records[0].payload["policy_number"] == "MULTI-1"
    assert "chunk_index" not in records[0].payload
