from __future__ import annotations

from typing import Any

from fastmcp.exceptions import ToolError

from domain.blueprints import BLUEPRINTS, resolve_stack


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
