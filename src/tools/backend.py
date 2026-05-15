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
            {
                "step": 1,
                "agent": agents[0],
                "task": "Design architecture and contracts",
            },
            {
                "step": 2,
                "agent": agents[1],
                "task": "Implement feature modules and tests",
            },
            {
                "step": 3,
                "agent": agents[2],
                "task": "Run review checklist and release readiness",
            },
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

    raise ToolError(
        "Could not infer stack. Mention Java, Node/Express/TypeScript, or Python/FastAPI."
    )


def list_document_blueprint_tool() -> dict[str, Any]:
    return {"document_processing": DOCUMENT_BLUEPRINT}


def generate_document_skill_set_tool(
    document_type: str, compliance_mode: str = "standard"
) -> dict[str, Any]:
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
            "Extract candidate identity, contact channels, role targets, work history, education, certifications, projects, languages, and skills",
            "Normalize date ranges, durations, seniority signals, technologies, and domain keywords",
            "Map evidence-backed skills to roles or projects instead of inferring unsupported competencies",
            "Flag missing chronology, unexplained gaps, overlapping periods, stale contact details, and low-confidence OCR spans",
        ],
        "insurance policy": [
            "Identify policyholder, insurer, policy number, effective dates, and renewal terms",
            "Extract coverage limits, deductibles, endorsements, exclusions, and waiting periods",
            "Summarize claim notice duties, required evidence, deadlines, and escalation paths",
            "Flag ambiguous clauses, missing schedules, and conflicts between declarations and endorsements",
        ],
    }
    checklist = checklists.get(
        doc_type,
        [
            "Classify document layout and language",
            "Extract key fields with confidence scores",
            "Validate required fields for downstream workflow",
        ],
    )

    return {
        "document_type": doc_type,
        "compliance_mode": compliance_mode,
        "priority_skills": DOCUMENT_BLUEPRINT["skills"],
        "checklist": checklist,
    }


def generate_document_agent_plan_tool(
    document_type: str, objective: str, constraints: str = ""
) -> dict[str, Any]:
    if not objective.strip():
        raise ToolError("objective must not be empty.")
    doc_type = document_type.strip().lower()
    if not doc_type:
        raise ToolError("document_type must not be empty.")

    agents = DOCUMENT_BLUEPRINT["agents"]
    plan = [
        {
            "step": 1,
            "agent": agents[0],
            "task": "Classify document and choose extraction pipeline",
        },
        {
            "step": 2,
            "agent": agents[1],
            "task": "Run OCR + structured field extraction with confidence scores",
        },
        {
            "step": 3,
            "agent": agents[2],
            "task": "Validate business rules, required fields, and anomaly checks",
        },
    ]
    if doc_type in {"insurance", "insurance policy", "policy"}:
        plan.append(
            {
                "step": 4,
                "agent": "insurance-document-reader-agent",
                "task": "Read policy language, summarize coverage, exclusions, limits, deductibles, and claim obligations",
            }
        )
    if doc_type in {"cv", "resume", "curriculum vitae"}:
        plan.append(
            {
                "step": 4,
                "agent": "cv-reader-agent",
                "task": "Read the CV, extract an evidence-backed candidate profile, normalize experience, and flag gaps or ambiguities",
            }
        )
    plan.append(
        {
            "step": len(plan) + 1,
            "agent": "document-review-agent",
            "task": "Generate review summary and remediation recommendations",
        }
    )
    return {
        "document_type": doc_type,
        "objective": objective,
        "constraints": constraints,
        "plan": plan,
    }


def generate_document_tool_spec_tool(capability: str) -> dict[str, Any]:
    cap = capability.strip().lower()
    if not cap:
        raise ToolError("capability must not be empty.")

    specs = {
        "insurance": {
            "name": "read_insurance_policy",
            "args": ["document_uri", "policy_profile", "jurisdiction"],
            "returns": [
                "coverage_summary",
                "exclusions",
                "claim_requirements",
                "warnings",
            ],
        },
        "cv": {
            "name": "read_cv",
            "args": ["document_uri", "role_profile", "language"],
            "returns": [
                "candidate_profile",
                "experience_timeline",
                "skills_matrix",
                "education",
                "warnings",
            ],
        },
        "resume": {
            "name": "read_cv",
            "args": ["document_uri", "role_profile", "language"],
            "returns": [
                "candidate_profile",
                "experience_timeline",
                "skills_matrix",
                "education",
                "warnings",
            ],
        },
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
    resolved = specs.get(
        cap,
        {
            "name": f"document_{cap}_tool",
            "args": ["payload"],
            "returns": ["result"],
        },
    )
    resolved["error_guidance"] = [
        "Return explicit field-level errors for extraction failures",
        "Include remediation hints when confidence is below threshold",
    ]
    return resolved


def resolve_document_processing_flow_tool(user_request: str) -> dict[str, Any]:
    text = user_request.strip().lower()
    if not text:
        raise ToolError("user_request must not be empty.")

    if "invoice" in text:
        return {
            "document_type": "invoice",
            "flow": "ap_invoice_automation",
            "reason": "Detected invoice processing intent.",
        }
    if "insurance" in text or "policy" in text or "coverage" in text or "claim" in text:
        return {
            "document_type": "insurance policy",
            "flow": "insurance_policy_reading",
            "reason": "Detected insurance policy reading intent.",
        }
    if "cv" in text or "resume" in text or "curriculum vitae" in text:
        return {
            "document_type": "curriculum vitae",
            "flow": "cv_reading",
            "agent": "cv-reader-agent",
            "skills": [
                "cv-reading",
                "candidate-profile-extraction",
                "experience-skills-normalization",
                "document-validation",
                "pii-redaction",
            ],
            "reason": "Detected CV/resume reading intent.",
        }

    return {
        "document_type": "generic_document",
        "flow": "generic_structured_extraction",
        "reason": "No specific type detected, using generic flow.",
    }


def list_platform_blueprints_tool() -> dict[str, Any]:
    return {"backend": BLUEPRINTS, "document_processing": DOCUMENT_BLUEPRINT}
