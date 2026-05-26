from services.document_persistence import (
    build_candidate_payload,
    build_insurance_payload,
    infer_pdf_domain,
)


def test_infer_pdf_domain_detects_cv() -> None:
    assert infer_pdf_domain("Work experience and education", "Summarize this CV") == "cv"


def test_infer_pdf_domain_detects_insurance() -> None:
    assert infer_pdf_domain("Policy number 123", "Explain insurance coverage") == "insurance"


def test_infer_pdf_domain_returns_other_for_unsupported_documents() -> None:
    assert infer_pdf_domain("Quarterly revenue and EBITDA", "Summarize this report") == "other"


def test_build_candidate_payload_extracts_contact_fields() -> None:
    payload = build_candidate_payload("Jane Doe\nEmail: jane@example.com\nPhone: +1 202 555 0110\nSenior engineer")

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
