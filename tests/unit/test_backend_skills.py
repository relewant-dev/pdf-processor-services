from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastmcp.exceptions import ToolError

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from server import list_backend_blueprints, resolve_backend_skill


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
