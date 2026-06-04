from __future__ import annotations

from typing import Any

from fastmcp import FastMCP
from clients.ollama import chat_with_ollama, ollama_health
from config import SERVICE_NAME
from logging_config import get_logger
from tools.blueprints import (
    generate_document_agent_plan_tool,
    generate_document_skill_set_tool,
    generate_document_tool_spec_tool,
    list_document_blueprint_tool,
    list_platform_blueprints_tool,
    resolve_document_processing_flow_tool,
)
from services.document_persistence import answer_document_prompt_from_database
from tools.document import extract_pdf_text, truncate_document_text

mcp = FastMCP(name=SERVICE_NAME, mask_error_details=True)
logger = get_logger()


@mcp.tool(description="Send a user prompt to local Ollama and return the model output.")
async def send_prompt(prompt: str) -> str:
    logger.info("Tool send_prompt called")
    return await chat_with_ollama(prompt)


@mcp.tool(
    description="Process a CV or insurance PDF through the database-first workflow."
)
async def process_pdf(file_path: str, question: str, max_chars: int = 30000) -> str:
    logger.info("Tool process_pdf called for file_path=%s", file_path)
    document_text = extract_pdf_text(file_path)
    truncated_text = truncate_document_text(document_text, max_chars=max_chars)
    workflow_result = await answer_document_prompt_from_database(truncated_text, question)
    return workflow_result.response


@mcp.tool(
    description="Check Ollama reachability and verify the configured model exists."
)
async def health_check() -> dict[str, Any]:
    logger.info("Tool health_check called")
    return await ollama_health()


@mcp.tool(description="List all document-processing platform blueprints.")
async def list_platform_blueprints() -> dict[str, Any]:
    logger.info("Tool list_platform_blueprints called")
    return list_platform_blueprints_tool()


@mcp.tool(description="List document-processing skills, agents, and tools.")
async def list_document_blueprint() -> dict[str, Any]:
    logger.info("Tool list_document_blueprint called")
    return list_document_blueprint_tool()


@mcp.tool(description="Generate a prioritized document-processing skill set.")
async def generate_document_skill_set(
    document_type: str, compliance_mode: str = "standard"
) -> dict[str, Any]:
    logger.info(
        "Tool generate_document_skill_set called for document_type=%s compliance_mode=%s",
        document_type,
        compliance_mode,
    )
    return generate_document_skill_set_tool(document_type, compliance_mode)


@mcp.tool(description="Generate an agent execution plan for document processing.")
async def generate_document_agent_plan(
    document_type: str, objective: str, constraints: str = ""
) -> dict[str, Any]:
    logger.info(
        "Tool generate_document_agent_plan called for document_type=%s", document_type
    )
    return generate_document_agent_plan_tool(document_type, objective, constraints)


@mcp.tool(description="Generate a tool contract for a document processing capability.")
async def generate_document_tool_spec(capability: str) -> dict[str, Any]:
    logger.info("Tool generate_document_tool_spec called for capability=%s", capability)
    return generate_document_tool_spec_tool(capability)


@mcp.tool(description="Resolve a request to a recommended document-processing flow.")
async def resolve_document_processing_flow(user_request: str) -> dict[str, Any]:
    logger.info("Tool resolve_document_processing_flow called")
    return resolve_document_processing_flow_tool(user_request)


@mcp.prompt
def chat_prompt(user_message: str) -> str:
    return f"User message: {user_message}"
