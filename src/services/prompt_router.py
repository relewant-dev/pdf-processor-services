from __future__ import annotations

import json
from typing import Any, Callable, Literal

from fastmcp.exceptions import ToolError
from pydantic import BaseModel, ConfigDict, Field

from clients.ollama import chat_with_ollama, ollama_health
from tools.backend import (
    generate_agent_plan_tool,
    generate_document_agent_plan_tool,
    generate_document_skill_set_tool,
    generate_document_tool_spec_tool,
    generate_skill_set_tool,
    list_backend_blueprints_tool,
    list_document_blueprint_tool,
    list_platform_blueprints_tool,
    resolve_backend_skill_tool,
    resolve_document_processing_flow_tool,
)

PromptCategory = Literal["backend", "document", "health", "chat"]


class PromptRoute(BaseModel):
    prompt: str
    category: PromptCategory
    tool_name: str
    reason: str


class PromptExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(
        ...,
        min_length=1,
        description="Frontend message to route, enrich with the inferred tool, and answer with Ollama.",
    )


class PromptExecutionResponse(BaseModel):
    response: str


def route_prompt(prompt: str) -> PromptRoute:
    text = prompt.strip().lower()
    if not text:
        raise ToolError("message must not be empty.")

    if any(token in text for token in ("health", "status", "ollama", "reachable")):
        return PromptRoute(
            prompt=prompt,
            category="health",
            tool_name="health_check",
            reason="Detected health/status intent.",
        )

    if any(
        token in text
        for token in (
            "invoice",
            "cv",
            "resume",
            "curriculum vitae",
            "document",
            "pdf",
            "ocr",
            "redact",
            "pii",
            "extract fields",
            "validate document",
        )
    ):
        return PromptRoute(
            prompt=prompt,
            category="document",
            tool_name="resolve_document_processing_flow",
            reason="Detected document-processing intent.",
        )

    if any(
        token in text
        for token in (
            "backend",
            "api",
            "java",
            "spring",
            "node",
            "express",
            "typescript",
            "python",
            "fastapi",
        )
    ):
        return PromptRoute(
            prompt=prompt,
            category="backend",
            tool_name="resolve_backend_skill",
            reason="Detected backend-generation intent.",
        )

    return PromptRoute(
        prompt=prompt,
        category="chat",
        tool_name="send_prompt",
        reason="No specialized tool intent detected; using general model chat.",
    )


def _argument(arguments: dict[str, Any], name: str, fallback: Any = None) -> Any:
    return arguments[name] if name in arguments else fallback


def _required_argument(arguments: dict[str, Any], name: str) -> Any:
    if name not in arguments or arguments[name] in (None, ""):
        raise ToolError(f"arguments.{name} is required for this tool.")
    return arguments[name]


async def execute_prompt_tool(
    request: PromptExecutionRequest,
) -> PromptExecutionResponse:
    route = route_prompt(request.message)

    if route.tool_name == "send_prompt":
        model_prompt = request.message
    else:
        tool_result = await _execute_tool(route.tool_name, request.message, {})
        model_prompt = _build_model_prompt(request.message, route, tool_result)

    model_result = await chat_with_ollama(model_prompt)
    return PromptExecutionResponse(response=model_result)


def _build_model_prompt(prompt: str, route: PromptRoute, tool_result: Any) -> str:
    tool_context = json.dumps(tool_result, indent=2, sort_keys=True)
    return (
        "Answer the user's prompt using the selected Smart IDE tool context. "
        "Return only the final answer for the user; do not mention routing metadata unless it is directly useful.\n\n"
        f"User prompt:\n{prompt}\n\n"
        "Selected tool context:\n"
        f"tool_name: {route.tool_name}\n"
        f"category: {route.category}\n"
        f"reason: {route.reason}\n"
        f"result:\n{tool_context}"
    )


async def _execute_tool(tool_name: str, prompt: str, arguments: dict[str, Any]) -> Any:
    async_tools: dict[str, Callable[[], Any]] = {
        "send_prompt": lambda: chat_with_ollama(str(_argument(arguments, "prompt", prompt))),
        "health_check": ollama_health,
    }
    if tool_name in async_tools:
        return await async_tools[tool_name]()

    sync_tools: dict[str, Callable[[], Any]] = {
        "list_backend_blueprints": list_backend_blueprints_tool,
        "list_platform_blueprints": list_platform_blueprints_tool,
        "list_document_blueprint": list_document_blueprint_tool,
        "resolve_backend_skill": lambda: resolve_backend_skill_tool(
            str(_argument(arguments, "user_request", prompt))
        ),
        "generate_skill_set": lambda: generate_skill_set_tool(
            str(_required_argument(arguments, "stack")),
            str(_argument(arguments, "project_type", "api")),
        ),
        "generate_agent_plan": lambda: generate_agent_plan_tool(
            str(_required_argument(arguments, "stack")),
            str(_argument(arguments, "feature_summary", prompt)),
            str(_argument(arguments, "constraints", "")),
        ),
        "resolve_document_processing_flow": lambda: resolve_document_processing_flow_tool(
            str(_argument(arguments, "user_request", prompt))
        ),
        "generate_document_skill_set": lambda: generate_document_skill_set_tool(
            str(_required_argument(arguments, "document_type")),
            str(_argument(arguments, "compliance_mode", "standard")),
        ),
        "generate_document_agent_plan": lambda: generate_document_agent_plan_tool(
            str(_required_argument(arguments, "document_type")),
            str(_argument(arguments, "objective", prompt)),
            str(_argument(arguments, "constraints", "")),
        ),
        "generate_document_tool_spec": lambda: generate_document_tool_spec_tool(
            str(_required_argument(arguments, "capability"))
        ),
    }
    if tool_name not in sync_tools:
        supported_tools = sorted([*async_tools.keys(), *sync_tools.keys()])
        raise ToolError(
            f"Unsupported tool_name '{tool_name}'. Use one of: {', '.join(supported_tools)}"
        )

    return sync_tools[tool_name]()
