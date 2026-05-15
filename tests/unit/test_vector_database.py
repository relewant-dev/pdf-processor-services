import pytest
from fastmcp.exceptions import ToolError

from domain.vector_records import CandidateRecord, InsuranceRecord
from repositories import vector_database
from repositories.vector_database import (
    CANDIDATES_COLLECTION,
    COLLECTION_SCHEMAS,
    INSURANCES_COLLECTION,
    _candidate_point_id,
    _insurance_point_id,
    validate_embedding,
)


def test_qdrant_collections_preserve_requested_payload_fields() -> None:
    assert set(COLLECTION_SCHEMAS) == {CANDIDATES_COLLECTION, INSURANCES_COLLECTION}
    assert "email" in COLLECTION_SCHEMAS[CANDIDATES_COLLECTION]["payload_fields"]
    assert "competences" in COLLECTION_SCHEMAS[CANDIDATES_COLLECTION]["payload_fields"]
    assert "insurance_number" in COLLECTION_SCHEMAS[INSURANCES_COLLECTION]["payload_fields"]
    assert "coverage_details" in COLLECTION_SCHEMAS[INSURANCES_COLLECTION]["payload_fields"]
    assert "source_document_text" in COLLECTION_SCHEMAS[INSURANCES_COLLECTION]["payload_fields"]


def test_validate_embedding_validates_qdrant_vector_size(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(vector_database, "VECTOR_SIZE", 3)

    assert validate_embedding([1, 2.5, 3]) == [1.0, 2.5, 3.0]

    with pytest.raises(ToolError, match="dimension mismatch"):
        validate_embedding([1, 2])


def test_point_ids_are_deterministic_for_unique_fields() -> None:
    candidate = CandidateRecord(first_name="Ada", last_name="Lovelace", email="ADA@example.com")
    same_candidate = CandidateRecord(first_name="Ada", last_name="Lovelace", email="ada@example.com")
    insurance = InsuranceRecord(
        insurance_number="POL-123",
        provider_name="Example Insurance",
        start_date="2026-01-01",
    )
    same_insurance = InsuranceRecord(
        insurance_number="pol-123",
        provider_name="Example Insurance",
        start_date="2026-01-01",
    )

    assert _candidate_point_id(candidate) == _candidate_point_id(same_candidate)
    assert _insurance_point_id(insurance) == _insurance_point_id(same_insurance)
