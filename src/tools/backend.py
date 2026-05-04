from __future__ import annotations

from typing import Any

from fastmcp.exceptions import ToolError

from domain.blueprints import BLUEPRINTS, DOCUMENT_BLUEPRINT, resolve_stack


def list_backend_blueprints_tool() -> dict[str, Any]:
    return {"stacks": BLUEPRINTS}


def generate_skill_set_tool(stack: str, project_type: str = "api") -> dict[str, Any]:
    stack_key = resolve_stack(stack)
    skills = BLUEPRINTS[stack_key]["skills"]
    return {
        "stack": stack_key,
        "project_type": project_type,
        "priority_skills": skills,
        "checklist": [
            "Define API contract and error schema",
            "Set auth/security and validation rules",
            "Implement observability and health endpoints",
            "Create unit and integration tests",
        ],
    }


def generate_agent_plan_tool(
    stack: str, feature_summary: str, constraints: str = ""
) -> dict[str, Any]:
    if not feature_summary.strip():
        raise ToolError("feature_summary must not be empty.")

    stack_key = resolve_stack(stack)
    agents = BLUEPRINTS[stack_key]["agents"]
    return {
        "stack": stack_key,
        "feature_summary": feature_summary,
        "constraints": constraints,
        "plan": [
            {"step": 1, "agent": agents[0], "task": "Design architecture and contracts"},
            {"step": 2, "agent": agents[1], "task": "Implement feature modules and tests"},
            {"step": 3, "agent": agents[2], "task": "Run review checklist and release readiness"},
        ],
    }


def resolve_backend_skill_tool(user_request: str) -> dict[str, str]:
    text = user_request.strip().lower()
    if not text:
        raise ToolError("user_request must not be empty.")

    if "java" in text or "spring" in text:
        return {
            "stack": "java_spring_boot",
            "skill": "generate-spring-boot-java-backend",
            "reason": "Detected Java/Spring intent.",
        }
    if "node" in text or "express" in text or "typescript" in text:
        return {
            "stack": "node_express_typescript",
            "skill": "generate-express-typescript-backend",
            "reason": "Detected Node/Express/TypeScript intent.",
        }
    if "python" in text or "fastapi" in text:
        return {
            "stack": "python_fastapi",
            "skill": "generate-fastapi-python-backend",
            "reason": "Detected Python/FastAPI intent.",
        }

    raise ToolError("Could not infer stack. Mention Java, Node/Express/TypeScript, or Python/FastAPI.")


def list_document_blueprint_tool() -> dict[str, Any]:
    return {"document_processing": DOCUMENT_BLUEPRINT}


def generate_document_skill_set_tool(document_type: str, compliance_mode: str = "standard") -> dict[str, Any]:
    doc_type = document_type.strip().lower()
    if not doc_type:
        raise ToolError("document_type must not be empty.")

    checklists: dict[str, list[str]] = {
        "invoice": [
            "Extract supplier, line items, taxes, totals",
            "Validate currency consistency and totals",
            "Flag duplicate invoice number risk",
        ],
        "curriculum vitae": [
            "Extract identity, roles, education, skills",
            "Normalize date ranges and durations",
            "Flag missing chronology and overlapping periods",
        ],
    }
    checklist = checklists.get(doc_type, [
        "Classify document layout and language",
        "Extract key fields with confidence scores",
        "Validate required fields for downstream workflow",
    ])

    return {
        "document_type": doc_type,
        "compliance_mode": compliance_mode,
        "priority_skills": DOCUMENT_BLUEPRINT["skills"],
        "checklist": checklist,
    }


def generate_document_agent_plan_tool(document_type: str, objective: str, constraints: str = "") -> dict[str, Any]:
    if not objective.strip():
        raise ToolError("objective must not be empty.")
    doc_type = document_type.strip().lower()
    if not doc_type:
        raise ToolError("document_type must not be empty.")

    agents = DOCUMENT_BLUEPRINT["agents"]
    return {
        "document_type": doc_type,
        "objective": objective,
        "constraints": constraints,
        "plan": [
            {"step": 1, "agent": agents[0], "task": "Classify document and choose extraction pipeline"},
            {"step": 2, "agent": agents[1], "task": "Run OCR + structured field extraction with confidence scores"},
            {"step": 3, "agent": agents[2], "task": "Validate business rules, required fields, and anomaly checks"},
            {"step": 4, "agent": agents[3], "task": "Generate review summary and remediation recommendations"},
        ],
    }


def generate_document_tool_spec_tool(capability: str) -> dict[str, Any]:
    cap = capability.strip().lower()
    if not cap:
        raise ToolError("capability must not be empty.")

    specs = {
        "extract": {
            "name": "extract_document_fields",
            "args": ["document_uri", "schema"],
            "returns": ["fields", "confidence", "warnings"],
        },
        "validate": {
            "name": "validate_document",
            "args": ["document_fields", "rule_profile"],
            "returns": ["valid", "violations", "risk_score"],
        },
        "redact": {
            "name": "redact_document",
            "args": ["document_uri", "pii_profile"],
            "returns": ["redacted_document_uri", "redaction_map"],
        },
    }
    resolved = specs.get(cap, {
        "name": f"document_{cap}_tool",
        "args": ["payload"],
        "returns": ["result"],
    })
    resolved["error_guidance"] = [
        "Return explicit field-level errors for extraction failures",
        "Include remediation hints when confidence is below threshold",
    ]
    return resolved


def resolve_document_processing_flow_tool(user_request: str) -> dict[str, str]:
    text = user_request.strip().lower()
    if not text:
        raise ToolError("user_request must not be empty.")

    if "invoice" in text:
        return {
            "document_type": "invoice",
            "flow": "ap_invoice_automation",
            "reason": "Detected invoice processing intent.",
        }
    if "cv" in text or "resume" in text or "curriculum vitae" in text:
        return {
            "document_type": "curriculum vitae",
            "flow": "candidate_profile_extraction",
            "reason": "Detected CV/resume processing intent.",
        }

    return {
        "document_type": "generic_document",
        "flow": "generic_structured_extraction",
        "reason": "No specific type detected, using generic flow.",
    }


def list_platform_blueprints_tool() -> dict[str, Any]:
    return {"backend": BLUEPRINTS, "document_processing": DOCUMENT_BLUEPRINT}
