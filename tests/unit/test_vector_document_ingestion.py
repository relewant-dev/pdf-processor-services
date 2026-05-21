import pytest

from services import vector_document_ingestion
from services.vector_document_ingestion import (
    _parse_json_object,
    process_candidate_pdf_to_vector_db,
    process_insurance_pdf_to_vector_db,
)


def test_parse_json_object_accepts_markdown_fenced_json() -> None:
    assert _parse_json_object('```json\n{"first_name":"Ada"}\n```') == {
        "first_name": "Ada"
    }


def test_validate_candidate_normalizes_competences_list() -> None:
    payload = {
        "first_name": "Ada",
        "last_name": "Lovelace",
        "competences": ["Python", "Java"],
    }

    candidate = vector_document_ingestion._validate_candidate(payload)

    assert candidate.competences == {"items": ["Python", "Java"]}


@pytest.mark.anyio
async def test_process_candidate_pdf_saves_cv_agent_result(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, object] = {}

    def fake_extract_pdf_text(file_path: str) -> str:
        calls["file_path"] = file_path
        return "Ada Lovelace CV Python SQL senior engineer"

    async def fake_chat_with_ollama(prompt: str) -> str:
        calls["prompt"] = prompt
        return """
        {
          "first_name": "Ada",
          "last_name": "Lovelace",
          "email": "ada@example.com",
          "phone": null,
          "seniority": "senior",
          "city": "London",
          "country": "UK",
          "address": null,
          "competences": {"programming": ["Python", "SQL"]},
          "previous_works": [],
          "education": [],
          "current_job_title": "Software Engineer",
          "current_company": "Analytical Engines Ltd",
          "availability_date": null
        }
        """

    async def fake_embed_with_ollama(text: str) -> list[float]:
        calls["embedding_text"] = text
        return [0.1, 0.2, 0.3]

    async def fake_save_candidate_record(candidate, source_document_text, embedding):
        calls["candidate"] = candidate
        calls["source_document_text"] = source_document_text
        calls["embedding"] = embedding
        return "candidate-id"

    monkeypatch.setattr(vector_document_ingestion, "extract_pdf_text", fake_extract_pdf_text)
    monkeypatch.setattr(vector_document_ingestion, "chat_with_ollama", fake_chat_with_ollama)
    monkeypatch.setattr(vector_document_ingestion, "embed_with_ollama", fake_embed_with_ollama)
    monkeypatch.setattr(vector_document_ingestion, "save_candidate_record", fake_save_candidate_record)

    result = await process_candidate_pdf_to_vector_db("/tmp/cv.pdf")

    assert result["agent"] == "cv-reader-agent"
    assert result["table"] == "candidates"
    assert result["id"] == "candidate-id"
    assert "CandidateRecord" in str(calls["prompt"])
    assert calls["embedding"] == [0.1, 0.2, 0.3]


@pytest.mark.anyio
async def test_process_insurance_pdf_saves_insurance_agent_result(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, object] = {}

    def fake_extract_pdf_text(file_path: str) -> str:
        calls["file_path"] = file_path
        return "Policy ABC health insurance active from 2026-01-01"

    async def fake_chat_with_ollama(prompt: str) -> str:
        calls["prompt"] = prompt
        return """
        {
          "insurance_number": "ABC-123",
          "candidate_id": null,
          "insurance_type": "health",
          "provider_name": "Example Insurance",
          "policy_holder_first_name": "Ada",
          "policy_holder_last_name": "Lovelace",
          "iban": null,
          "bic_swift": null,
          "monthly_price": "99.90",
          "annual_price": null,
          "currency": "EUR",
          "coverage_details": {"medical": true},
          "start_date": "2026-01-01",
          "end_date": null,
          "renewal_date": null,
          "status": "active",
          "payment_frequency": "monthly",
          "last_payment_date": null,
          "beneficiary": {},
          "documents": [],
          "notes": null
        }
        """

    async def fake_embed_with_ollama(text: str) -> list[float]:
        calls["embedding_text"] = text
        return [0.1, 0.2, 0.3]

    async def fake_save_insurance_record(insurance, source_document_text, embedding):
        calls["insurance"] = insurance
        calls["source_document_text"] = source_document_text
        calls["embedding"] = embedding
        return "insurance-id"

    monkeypatch.setattr(vector_document_ingestion, "extract_pdf_text", fake_extract_pdf_text)
    monkeypatch.setattr(vector_document_ingestion, "chat_with_ollama", fake_chat_with_ollama)
    monkeypatch.setattr(vector_document_ingestion, "embed_with_ollama", fake_embed_with_ollama)
    monkeypatch.setattr(vector_document_ingestion, "save_insurance_record", fake_save_insurance_record)

    result = await process_insurance_pdf_to_vector_db("/tmp/policy.pdf")

    assert result["agent"] == "insurance-document-reader-agent"
    assert result["table"] == "insurances"
    assert result["id"] == "insurance-id"
    assert "InsuranceRecord" in str(calls["prompt"])
    assert calls["embedding"] == [0.1, 0.2, 0.3]
