from __future__ import annotations

DOCUMENT_BLUEPRINT: dict[str, list[str]] = {
    "skills": [
        "document-classification",
        "ocr-extraction",
        "structured-data-mapping",
        "pii-redaction",
        "document-validation",
        "fraud-signals-detection",
        "insurance-policy-reading",
        "coverage-exclusions-analysis",
        "claims-requirements-extraction",
        "cv-reading",
        "candidate-profile-extraction",
        "experience-skills-normalization",
        "document-processing-observability",
    ],
    "agents": [
        "document-intake-agent",
        "document-extraction-agent",
        "document-validation-agent",
        "insurance-document-reader-agent",
        "cv-reader-agent",
        "document-review-agent",
    ],
    "tools": [
        "list_document_blueprint",
        "generate_document_skill_set",
        "generate_document_agent_plan",
        "generate_document_tool_spec",
        "resolve_document_processing_flow",
    ],
}
