from __future__ import annotations

from fastmcp.exceptions import ToolError

BLUEPRINTS: dict[str, dict[str, list[str]]] = {
    "java_spring_boot": {
        "skills": [
            "api-design",
            "auth-security",
            "data-modeling",
            "testing-strategy",
            "observability",
            "spring-api-implementation",
            "generate-spring-boot-java-backend",
            "spring-data-jpa",
            "spring-boot-hardening",
        ],
        "agents": [
            "backend-architect-agent",
            "spring-implementation-agent",
            "backend-review-agent",
        ],
    },
    "node_express_typescript": {
        "skills": [
            "api-design",
            "auth-security",
            "data-modeling",
            "testing-strategy",
            "observability",
            "express-route-architecture",
            "generate-express-typescript-backend",
            "typescript-domain-modeling",
            "node-runtime-reliability",
        ],
        "agents": [
            "backend-architect-agent",
            "express-ts-implementation-agent",
            "backend-review-agent",
        ],
    },
    "python_fastapi": {
        "skills": [
            "api-design",
            "auth-security",
            "data-modeling",
            "testing-strategy",
            "observability",
            "fastapi-endpoint-design",
            "generate-fastapi-python-backend",
            "fastapi-async-io",
            "python-service-operations",
        ],
        "agents": [
            "backend-architect-agent",
            "fastapi-implementation-agent",
            "backend-review-agent",
        ],
    },
}


def normalize_stack(stack: str) -> str:
    return stack.strip().lower().replace("-", "_").replace(" ", "_")


def resolve_stack(stack: str) -> str:
    key = normalize_stack(stack)
    aliases = {
        "java": "java_spring_boot",
        "spring_boot": "java_spring_boot",
        "nodejs": "node_express_typescript",
        "node": "node_express_typescript",
        "express": "node_express_typescript",
        "typescript": "node_express_typescript",
        "python": "python_fastapi",
        "fastapi": "python_fastapi",
    }
    key = aliases.get(key, key)
    if key not in BLUEPRINTS:
        raise ToolError(
            f"Unsupported stack '{stack}'. Use one of: {', '.join(BLUEPRINTS.keys())}"
        )
    return key


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
        "document-processing-observability",
    ],
    "agents": [
        "document-intake-agent",
        "document-extraction-agent",
        "document-validation-agent",
        "insurance-document-reader-agent",
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
