from __future__ import annotations

import json
from typing import Any, Literal

from fastmcp.exceptions import ToolError
from pydantic import ValidationError

from clients.ollama import chat_with_ollama, embed_with_ollama
from domain.vector_records import CandidateRecord, InsuranceRecord
from logging_config import get_logger
from repositories.vector_database import save_candidate_record, save_insurance_record
from tools.document import extract_pdf_text, truncate_document_text

DocumentAgent = Literal["cv-reader-agent", "insurance-document-reader-agent"]
logger = get_logger()


async def process_candidate_pdf_to_vector_db(
    file_path: str,
    max_chars: int = 30000,
) -> dict[str, Any]:
    logger.info("Processing candidate PDF for vector DB file_path=%s", file_path)
    document_text = truncate_document_text(
        extract_pdf_text(file_path), max_chars=max_chars
    )
    extracted = await _extract_structured_json(
        document_text=document_text,
        agent="cv-reader-agent",
        schema_name="CandidateRecord",
        instructions=(
            "Extract the candidate profile from the CV/resume. Return JSON only with keys: "
            "first_name, last_name, email, phone, seniority, city, country, address, "
            "competences, previous_works, education, current_job_title, current_company, "
            "availability_date. Use null for unknown optional scalar values, {} for unknown "
            "objects, and [] for unknown lists. Do not invent facts. Dates must be ISO dates."
        ),
    )
    candidate = _validate_candidate(extracted)
    embedding = await embed_with_ollama(
        _candidate_embedding_text(candidate, document_text)
    )
    candidate_id = await save_candidate_record(candidate, document_text, embedding)
    return {
        "agent": "cv-reader-agent",
        "table": "candidates",
        "id": candidate_id,
        "record": candidate.model_dump(mode="json"),
    }


async def process_insurance_pdf_to_vector_db(
    file_path: str,
    max_chars: int = 30000,
) -> dict[str, Any]:
    logger.info("Processing insurance PDF for vector DB file_path=%s", file_path)
    document_text = truncate_document_text(
        extract_pdf_text(file_path), max_chars=max_chars
    )
    extracted = await _extract_structured_json(
        document_text=document_text,
        agent="insurance-document-reader-agent",
        schema_name="InsuranceRecord",
        instructions=(
            "Extract the insurance policy from the document. Return JSON only with keys: "
            "insurance_number, candidate_id, insurance_type, provider_name, "
            "policy_holder_first_name, policy_holder_last_name, iban, bic_swift, "
            "monthly_price, "
            "annual_price, currency, coverage_details, start_date, end_date, renewal_date, "
            "status, payment_frequency, last_payment_date, beneficiary, documents, notes. "
            "Use null for unknown optional scalar values, {} for unknown objects, and [] for "
            "unknown lists. Do not invent facts. Dates must be ISO dates."
        ),
    )
    insurance = _validate_insurance(extracted)
    embedding = await embed_with_ollama(
        _insurance_embedding_text(insurance, document_text)
    )
    insurance_id = await save_insurance_record(insurance, document_text, embedding)
    return {
        "agent": "insurance-document-reader-agent",
        "table": "insurances",
        "id": insurance_id,
        "record": insurance.model_dump(mode="json"),
    }


async def _extract_structured_json(
    document_text: str,
    agent: DocumentAgent,
    schema_name: str,
    instructions: str,
) -> dict[str, Any]:
    logger.debug("Extracting structured JSON with agent=%s schema=%s", agent, schema_name)
    prompt = (
        f"You are {agent}. Extract a {schema_name} from the PDF text.\n"
        f"{instructions}\n\n"
        "Return one valid JSON object and no markdown fences.\n\n"
        f"PDF text:\n{document_text}"
    )
    raw_response = await chat_with_ollama(prompt)
    return _parse_json_object(raw_response)


def _parse_json_object(raw_response: str) -> dict[str, Any]:
    text = raw_response.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1]).strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        logger.error("Model response is not valid JSON for vector persistence.")
        raise ToolError(
            "Model did not return valid JSON for vector database persistence."
        ) from exc
    if not isinstance(value, dict):
        raise ToolError(
            "Model must return one JSON object for vector database persistence."
        )
    return value


def _validate_candidate(payload: dict[str, Any]) -> CandidateRecord:
    try:
        return CandidateRecord.model_validate(payload)
    except ValidationError as exc:
        logger.error("Candidate payload validation failed.")
        raise ToolError(
            f"Candidate extraction did not match the candidates schema: {exc}"
        ) from exc


def _validate_insurance(payload: dict[str, Any]) -> InsuranceRecord:
    try:
        return InsuranceRecord.model_validate(payload)
    except ValidationError as exc:
        logger.error("Insurance payload validation failed.")
        raise ToolError(
            f"Insurance extraction did not match the insurances schema: {exc}"
        ) from exc


def _candidate_embedding_text(candidate: CandidateRecord, document_text: str) -> str:
    return (
        json.dumps(candidate.model_dump(mode="json"), sort_keys=True)
        + "\n\n"
        + document_text
    )


def _insurance_embedding_text(insurance: InsuranceRecord, document_text: str) -> str:
    return (
        json.dumps(insurance.model_dump(mode="json"), sort_keys=True)
        + "\n\n"
        + document_text
    )
