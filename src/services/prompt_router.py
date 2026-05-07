from __future__ import annotations

from typing import Any, Callable, Literal

from fastmcp.exceptions import ToolError
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

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

    prompt: str = Field(
        ...,
        min_length=1,
        validation_alias=AliasChoices("message", "prompt"),
        description="Frontend message to route and execute with the inferred tool.",
    )
    arguments: dict[str, Any] = Field(default_factory=dict)


class PromptExecutionResponse(BaseModel):
    prompt: str
    tool_name: str
    arguments: dict[str, Any]
    result: Any


def route_prompt(prompt: str) -> PromptRoute:
    text = prompt.strip().lower()
    if not text:
        raise ToolError("prompt must not be empty.")

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
    route = route_prompt(request.prompt)
    tool_name = route.tool_name
    arguments = dict(request.arguments)

    result = await _execute_tool(tool_name, request.prompt, arguments)

    return PromptExecutionResponse(
        prompt=request.prompt,
        tool_name=tool_name,
        arguments=arguments,
        result=result,
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
