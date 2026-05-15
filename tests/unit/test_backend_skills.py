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
    list_backend_blueprints,
    list_platform_blueprints,
    resolve_backend_skill,
    resolve_document_processing_flow,
)


@pytest.mark.anyio
async def test_resolve_backend_skill_java() -> None:
    result = await resolve_backend_skill("Create a backend in Java")
    assert result["stack"] == "java_spring_boot"
    assert result["skill"] == "generate-spring-boot-java-backend"


@pytest.mark.anyio
async def test_resolve_backend_skill_node() -> None:
    result = await resolve_backend_skill("Build Node API with Express and TypeScript")
    assert result["stack"] == "node_express_typescript"
    assert result["skill"] == "generate-express-typescript-backend"


@pytest.mark.anyio
async def test_resolve_backend_skill_python() -> None:
    result = await resolve_backend_skill("Need a Python FastAPI backend")
    assert result["stack"] == "python_fastapi"
    assert result["skill"] == "generate-fastapi-python-backend"


@pytest.mark.anyio
async def test_resolve_backend_skill_invalid() -> None:
    with pytest.raises(ToolError):
        await resolve_backend_skill("Create backend in Elixir")


@pytest.mark.anyio
async def test_list_backend_blueprints_contains_skills() -> None:
    data = await list_backend_blueprints()
    assert "stacks" in data
    assert "java_spring_boot" in data["stacks"]
    assert "generate-spring-boot-java-backend" in data["stacks"]["java_spring_boot"]["skills"]


@pytest.mark.anyio
async def test_list_platform_blueprints_contains_backend_and_document() -> None:
    data = await list_platform_blueprints()
    assert "backend" in data
    assert "document_processing" in data
    assert "python_fastapi" in data["backend"]
    assert "ocr-extraction" in data["document_processing"]["skills"]


@pytest.mark.anyio
async def test_list_platform_blueprints_contains_insurance_agent_and_skills() -> None:
    data = await list_platform_blueprints()

    document_processing = data["document_processing"]

    assert "insurance-document-reader-agent" in document_processing["agents"]
    assert "insurance-policy-reading" in document_processing["skills"]
    assert "coverage-exclusions-analysis" in document_processing["skills"]
    assert "claims-requirements-extraction" in document_processing["skills"]


@pytest.mark.anyio
async def test_resolve_document_processing_flow_detects_insurance_policy() -> None:
    result = await resolve_document_processing_flow(
        "Read this insurance policy and summarize coverage exclusions"
    )

    assert result["document_type"] == "insurance policy"
    assert result["flow"] == "insurance_policy_reading"


@pytest.mark.anyio
async def test_generate_document_skill_set_for_insurance_policy() -> None:
    result = await generate_document_skill_set("insurance policy")

    assert result["document_type"] == "insurance policy"
    assert "insurance-policy-reading" in result["priority_skills"]
    assert any("coverage limits" in item for item in result["checklist"])


@pytest.mark.anyio
async def test_generate_document_agent_plan_uses_insurance_reader_agent() -> None:
    result = await generate_document_agent_plan(
        "insurance policy",
        "Summarize covered events and claim requirements",
    )

    agents = [step["agent"] for step in result["plan"]]

    assert "insurance-document-reader-agent" in agents
    assert agents[-1] == "document-review-agent"


@pytest.mark.anyio
async def test_generate_document_tool_spec_for_insurance_capability() -> None:
    result = await generate_document_tool_spec("insurance")

    assert result["name"] == "read_insurance_policy"
    assert "coverage_summary" in result["returns"]
    assert "claim_requirements" in result["returns"]
