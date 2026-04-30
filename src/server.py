from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from clients.ollama import chat_with_ollama, ollama_health
from config import SERVICE_NAME
from logging_config import get_logger
from tools.backend import (
    generate_agent_plan_tool,
    generate_skill_set_tool,
    list_backend_blueprints_tool,
    resolve_backend_skill_tool,
)

mcp = FastMCP(name=SERVICE_NAME, mask_error_details=True)
logger = get_logger()


@mcp.tool(description="Send a user prompt to local Ollama and return the model output.")
async def send_prompt(prompt: str) -> str:
    logger.info("Tool send_prompt called")
    return await chat_with_ollama(prompt)


@mcp.tool(description="Check Ollama reachability and verify the configured model exists.")
async def health_check() -> dict[str, Any]:
    logger.info("Tool health_check called")
    return await ollama_health()


@mcp.tool(description="List supported backend blueprints, skills, and agents.")
async def list_backend_blueprints() -> dict[str, Any]:
    logger.info("Tool list_backend_blueprints called")
    return list_backend_blueprints_tool()


@mcp.tool(description="Generate a prioritized skill set for a backend stack.")
async def generate_skill_set(stack: str, project_type: str = "api") -> dict[str, Any]:
    logger.info("Tool generate_skill_set called for stack=%s project_type=%s", stack, project_type)
    return generate_skill_set_tool(stack, project_type)


@mcp.tool(description="Generate an agent execution plan for a backend feature.")
async def generate_agent_plan(
    stack: str, feature_summary: str, constraints: str = ""
) -> dict[str, Any]:
    logger.info("Tool generate_agent_plan called for stack=%s", stack)
    return generate_agent_plan_tool(stack, feature_summary, constraints)


@mcp.tool(description="Resolve a user request to a recommended backend generation skill.")
async def resolve_backend_skill(user_request: str) -> dict[str, str]:
    logger.info("Tool resolve_backend_skill called")
    return resolve_backend_skill_tool(user_request)


@mcp.prompt
def chat_prompt(user_message: str) -> str:
    return f"User message: {user_message}"


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
