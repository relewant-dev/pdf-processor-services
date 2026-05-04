from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastmcp.exceptions import ToolError

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from server import (
    generate_document_agent_plan,
    generate_document_skill_set,
    generate_document_tool_spec,
    list_document_blueprint,
    resolve_document_processing_flow,
)


@pytest.mark.anyio
async def test_list_document_blueprint_contains_invoice_tools() -> None:
    data = await list_document_blueprint()
    assert "document_processing" in data
    assert "generate_document_skill_set" in data["document_processing"]["tools"]


@pytest.mark.anyio
async def test_generate_document_skill_set_invoice() -> None:
    result = await generate_document_skill_set("invoice")
    assert result["document_type"] == "invoice"
    assert "ocr-extraction" in result["priority_skills"]


@pytest.mark.anyio
async def test_generate_document_agent_plan_requires_objective() -> None:
    with pytest.raises(ToolError):
        await generate_document_agent_plan("invoice", "")


@pytest.mark.anyio
async def test_generate_document_tool_spec_extract() -> None:
    result = await generate_document_tool_spec("extract")
    assert result["name"] == "extract_document_fields"
    assert "error_guidance" in result


@pytest.mark.anyio
async def test_resolve_document_processing_flow_cv() -> None:
    result = await resolve_document_processing_flow("parse this curriculum vitae into json")
    assert result["flow"] == "candidate_profile_extraction"
