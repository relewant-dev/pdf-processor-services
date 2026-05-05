from __future__ import annotations

from typing import Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from clients.ollama import chat_with_ollama, ollama_health
from config import SERVICE_NAME
from logging_config import get_logger
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
from tools.document import build_document_prompt, extract_pdf_text

mcp = FastMCP(name=SERVICE_NAME, mask_error_details=True)
logger = get_logger()


@mcp.tool(description="Send a user prompt to local Ollama and return the model output.")
async def send_prompt(prompt: str) -> str:
    logger.info("Tool send_prompt called")
    return await chat_with_ollama(prompt)


@mcp.tool(description="Extract text from a PDF file and answer a question using local Ollama.")
async def process_pdf(file_path: str, question: str) -> str:
    logger.info("Tool process_pdf called for file_path=%s", file_path)
    document_text = extract_pdf_text(file_path)
    prompt = build_document_prompt(document_text, question)
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
async def generate_agent_plan(stack: str, feature_summary: str, constraints: str = "") -> dict[str, Any]:
    logger.info("Tool generate_agent_plan called for stack=%s", stack)
    return generate_agent_plan_tool(stack, feature_summary, constraints)


@mcp.tool(description="Resolve a user request to a recommended backend generation skill.")
async def resolve_backend_skill(user_request: str) -> dict[str, str]:
    logger.info("Tool resolve_backend_skill called")
    return resolve_backend_skill_tool(user_request)




@mcp.tool(description="List all platform blueprints (backend + document processing).")
async def list_platform_blueprints() -> dict[str, Any]:
    logger.info("Tool list_platform_blueprints called")
    return list_platform_blueprints_tool()


@mcp.tool(description="List document-processing skills, agents, and tools.")
async def list_document_blueprint() -> dict[str, Any]:
    logger.info("Tool list_document_blueprint called")
    return list_document_blueprint_tool()


@mcp.tool(description="Generate a prioritized document-processing skill set.")
async def generate_document_skill_set(document_type: str, compliance_mode: str = "standard") -> dict[str, Any]:
    logger.info("Tool generate_document_skill_set called for document_type=%s compliance_mode=%s", document_type, compliance_mode)
    return generate_document_skill_set_tool(document_type, compliance_mode)


@mcp.tool(description="Generate an agent execution plan for document processing.")
async def generate_document_agent_plan(document_type: str, objective: str, constraints: str = "") -> dict[str, Any]:
    logger.info("Tool generate_document_agent_plan called for document_type=%s", document_type)
    return generate_document_agent_plan_tool(document_type, objective, constraints)


@mcp.tool(description="Generate a tool contract for a document processing capability.")
async def generate_document_tool_spec(capability: str) -> dict[str, Any]:
    logger.info("Tool generate_document_tool_spec called for capability=%s", capability)
    return generate_document_tool_spec_tool(capability)


@mcp.tool(description="Resolve a request to a recommended document-processing flow.")
async def resolve_document_processing_flow(user_request: str) -> dict[str, str]:
    logger.info("Tool resolve_document_processing_flow called")
    return resolve_document_processing_flow_tool(user_request)


@mcp.prompt
def chat_prompt(user_message: str) -> str:
    return f"User message: {user_message}"
