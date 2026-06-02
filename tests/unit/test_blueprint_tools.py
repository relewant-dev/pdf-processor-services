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
    list_platform_blueprints,
    resolve_document_processing_flow,
)


@pytest.mark.anyio
async def test_list_platform_blueprints_contains_document_processing() -> None:
    data = await list_platform_blueprints()
    assert "document_processing" in data
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
async def test_list_platform_blueprints_contains_cv_agent_and_skills() -> None:
    data = await list_platform_blueprints()

    document_processing = data["document_processing"]

    assert "cv-reader-agent" in document_processing["agents"]
    assert "cv-reading" in document_processing["skills"]
    assert "candidate-profile-extraction" in document_processing["skills"]
    assert "experience-skills-normalization" in document_processing["skills"]


@pytest.mark.anyio
async def test_resolve_document_processing_flow_detects_cv_reading() -> None:
    result = await resolve_document_processing_flow(
        "Read this CV and summarize candidate skills"
    )

    assert result["document_type"] == "curriculum vitae"
    assert result["flow"] == "cv_reading"
    assert result["agent"] == "cv-reader-agent"
    assert "cv-reading" in result["skills"]


@pytest.mark.anyio
async def test_generate_document_skill_set_for_curriculum_vitae() -> None:
    result = await generate_document_skill_set("curriculum vitae")

    assert result["document_type"] == "curriculum vitae"
    assert "cv-reading" in result["priority_skills"]
    assert any("candidate identity" in item for item in result["checklist"])


@pytest.mark.anyio
async def test_generate_document_agent_plan_uses_cv_reader_agent() -> None:
    result = await generate_document_agent_plan(
        "curriculum vitae",
        "Extract a candidate profile and normalize skills",
    )

    agents = [step["agent"] for step in result["plan"]]

    assert "cv-reader-agent" in agents
    assert agents[-1] == "document-review-agent"


@pytest.mark.anyio
async def test_generate_document_tool_spec_for_cv_capability() -> None:
    result = await generate_document_tool_spec("cv")

    assert result["name"] == "read_cv"
    assert "candidate_profile" in result["returns"]
    assert "skills_matrix" in result["returns"]


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
