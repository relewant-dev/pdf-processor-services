from __future__ import annotations

import os
from typing import Any

import httpx
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

SERVICE_NAME = "smart-ide-services"
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5vl:7b")

mcp = FastMCP(name=SERVICE_NAME, mask_error_details=True)

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


def _normalize_stack(stack: str) -> str:
    return stack.strip().lower().replace("-", "_").replace(" ", "_")


def _resolve_stack(stack: str) -> str:
    key = _normalize_stack(stack)
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


async def _chat_with_ollama(prompt: str) -> str:
    """Send a prompt to the local Ollama instance and return generated text."""
    if not prompt.strip():
        raise ToolError("Prompt must not be empty.")

    payload: dict[str, Any] = {
        "model": OLLAMA_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(f"{OLLAMA_URL}/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        raise ToolError(
            f"Failed to reach Ollama at {OLLAMA_URL}. Ensure 'ollama serve' is running."
        ) from exc

    message = data.get("message", {})
    content = message.get("content")
    if not content:
        raise ToolError("Ollama returned an unexpected response shape.")
    return content


@mcp.tool(description="Send a user prompt to local Ollama and return the model output.")
async def send_prompt(prompt: str) -> str:
    """Receives a user prompt and returns model output from local Ollama."""
    return await _chat_with_ollama(prompt)


@mcp.tool(description="Check Ollama reachability and verify the configured model exists.")
async def health_check() -> dict[str, Any]:
    """Checks if Ollama is reachable and the configured model exists locally."""
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            tags_resp = await client.get(f"{OLLAMA_URL}/api/tags")
            tags_resp.raise_for_status()
            models = tags_resp.json().get("models", [])
    except httpx.HTTPError as exc:
        raise ToolError(
            f"Ollama is not reachable at {OLLAMA_URL}. Start it with: ollama serve"
        ) from exc

    has_model = any(model.get("name") == OLLAMA_MODEL for model in models)
    return {
        "ollama_url": OLLAMA_URL,
        "model": OLLAMA_MODEL,
        "model_available": has_model,
        "next_step": None if has_model else f"ollama pull {OLLAMA_MODEL}",
    }


@mcp.tool(description="List supported backend blueprints, skills, and agents.")
async def list_backend_blueprints() -> dict[str, Any]:
    """Return supported backend stacks and their skill/agent bundles."""
    return {"stacks": BLUEPRINTS}


@mcp.tool(description="Generate a prioritized skill set for a backend stack.")
async def generate_skill_set(stack: str, project_type: str = "api") -> dict[str, Any]:
    """Return recommended skill ordering for a selected stack."""
    stack_key = _resolve_stack(stack)
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


@mcp.tool(description="Generate an agent execution plan for a backend feature.")
async def generate_agent_plan(
    stack: str, feature_summary: str, constraints: str = ""
) -> dict[str, Any]:
    """Return a role-based implementation plan for a feature request."""
    if not feature_summary.strip():
        raise ToolError("feature_summary must not be empty.")

    stack_key = _resolve_stack(stack)
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


@mcp.tool(description="Resolve a user request to a recommended backend generation skill.")
async def resolve_backend_skill(user_request: str) -> dict[str, str]:
    """Map plain-language requests to a stack-specific backend generation skill."""
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


@mcp.prompt
def chat_prompt(user_message: str) -> str:
    """Create a reusable prompt template for user chat messages."""
    return f"User message: {user_message}"


def main() -> None:
    """Run as an MCP service (stdio transport by default)."""
    mcp.run()


if __name__ == "__main__":
    main()
