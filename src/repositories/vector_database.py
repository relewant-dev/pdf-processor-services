from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence
from uuid import NAMESPACE_URL, uuid4, uuid5

from fastmcp.exceptions import ToolError

from config import QDRANT_API_KEY, QDRANT_TIMEOUT_SECONDS, QDRANT_URL, VECTOR_SIZE
from domain.vector_records import CandidateRecord, InsuranceRecord
from logging_config import get_logger

CANDIDATES_COLLECTION = "candidates"
INSURANCES_COLLECTION = "insurances"
VECTOR_DISTANCE = "Cosine"
logger = get_logger()

COLLECTION_SCHEMAS: dict[str, dict[str, Any]] = {
    CANDIDATES_COLLECTION: {
        "description": "CV/resume extraction output written by cv-reader-agent.",
        "payload_fields": [
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
            "source_document_text",
            "created_at",
            "updated_at",
        ],
    },
    INSURANCES_COLLECTION: {
        "description": "Insurance extraction output written by insurance-document-reader-agent.",
        "payload_fields": [
            "id",
            "insurance_number",
            "candidate_id",
            "insurance_type",
            "provider_name",
            "policy_holder_first_name",
            "policy_holder_last_name",
            "iban",
            "bic_swift",
            "monthly_price",
            "annual_price",
            "currency",
            "coverage_details",
            "start_date",
            "end_date",
            "renewal_date",
            "status",
            "payment_frequency",
            "last_payment_date",
            "beneficiary",
            "documents",
            "notes",
            "source_document_text",
            "created_at",
            "updated_at",
        ],
    },
}


def validate_embedding(embedding: Sequence[float]) -> list[float]:
    logger.debug("Validating embedding vector with length=%s", len(embedding))
    if not embedding:
        raise ToolError("Embedding vector must not be empty.")
    if len(embedding) != VECTOR_SIZE:
        raise ToolError(
            f"Embedding vector dimension mismatch: expected {VECTOR_SIZE}, "
            f"got {len(embedding)}."
        )
    return [float(value) for value in embedding]


async def init_vector_database() -> None:
    logger.info(
        "Initializing vector database at url=%s for collections=%s",
        QDRANT_URL,
        ", ".join((CANDIDATES_COLLECTION, INSURANCES_COLLECTION)),
    )
    client = _build_qdrant_client()
    try:
        await _ensure_collection(client, CANDIDATES_COLLECTION)
        await _ensure_collection(client, INSURANCES_COLLECTION)
    finally:
        await client.close()


async def save_candidate_record(
    candidate: CandidateRecord,
    source_document_text: str,
    embedding: Sequence[float],
) -> str:
    logger.info("Saving candidate record to collection=%s", CANDIDATES_COLLECTION)
    vector = validate_embedding(embedding)
    point_id = _candidate_point_id(candidate)
    payload = _build_payload(candidate.model_dump(mode="json"), source_document_text, point_id)
    await _upsert_point(CANDIDATES_COLLECTION, point_id, vector, payload)
    return point_id


async def save_insurance_record(
    insurance: InsuranceRecord,
    source_document_text: str,
    embedding: Sequence[float],
) -> str:
    logger.info("Saving insurance record to collection=%s", INSURANCES_COLLECTION)
    vector = validate_embedding(embedding)
    point_id = _insurance_point_id(insurance)
    payload = _build_payload(insurance.model_dump(mode="json"), source_document_text, point_id)
    await _upsert_point(INSURANCES_COLLECTION, point_id, vector, payload)
    return point_id


async def _ensure_collection(client: Any, collection_name: str) -> None:
    qdrant_models = _load_qdrant_models()
    exists = await client.collection_exists(collection_name=collection_name)
    if exists:
        logger.debug("Collection already exists: %s", collection_name)
        return

    logger.info(
        "Creating missing collection=%s with vector_size=%s distance=%s",
        collection_name,
        VECTOR_SIZE,
        VECTOR_DISTANCE,
    )
    await client.create_collection(
        collection_name=collection_name,
        vectors_config=qdrant_models.VectorParams(
            size=VECTOR_SIZE,
            distance=qdrant_models.Distance.COSINE,
        ),
    )


async def _upsert_point(
    collection_name: str,
    point_id: str,
    vector: list[float],
    payload: dict[str, Any],
) -> None:
    logger.info(
        "Upserting point id=%s into collection=%s payload_keys=%s",
        point_id,
        collection_name,
        sorted(payload.keys()),
    )
    client = _build_qdrant_client()
    qdrant_models = _load_qdrant_models()
    try:
        await _ensure_collection(client, collection_name)
        await client.upsert(
            collection_name=collection_name,
            points=[
                qdrant_models.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload,
                )
            ],
            wait=True,
        )
    finally:
        await client.close()


def _build_payload(record: dict[str, Any], source_document_text: str, point_id: str) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": point_id,
        **record,
        "source_document_text": source_document_text,
        "created_at": now,
        "updated_at": now,
    }


def _candidate_point_id(candidate: CandidateRecord) -> str:
    if candidate.email:
        return str(uuid5(NAMESPACE_URL, f"candidate:{candidate.email.lower()}"))
    return str(uuid4())


def _insurance_point_id(insurance: InsuranceRecord) -> str:
    return str(uuid5(NAMESPACE_URL, f"insurance:{insurance.insurance_number.lower()}"))


def _build_qdrant_client() -> Any:
    logger.debug(
        "Building Qdrant client for url=%s timeout=%ss",
        QDRANT_URL,
        QDRANT_TIMEOUT_SECONDS,
    )
    qdrant_client_module = _load_qdrant_client_module()
    return qdrant_client_module.AsyncQdrantClient(
        url=QDRANT_URL,
        api_key=QDRANT_API_KEY or None,
        timeout=QDRANT_TIMEOUT_SECONDS,
    )


def _load_qdrant_client_module() -> Any:
    from importlib.util import find_spec

    if find_spec("qdrant_client") is None:
        logger.error("qdrant-client dependency is missing.")
        raise ToolError(
            "qdrant-client is required for vector database persistence. "
            "Install project dependencies with `python -m pip install -e .`."
        )

    import qdrant_client

    return qdrant_client


def _load_qdrant_models() -> Any:
    _load_qdrant_client_module()

    from qdrant_client import models

    return models
