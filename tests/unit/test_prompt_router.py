from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastmcp.exceptions import ToolError
from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from http_api import create_app
from services.prompt_router import PromptExecutionRequest, execute_prompt_tool, route_prompt


def test_route_prompt_detects_backend_intent() -> None:
    route = route_prompt("Create a Python FastAPI backend")

    assert route.category == "backend"
    assert route.tool_name == "resolve_backend_skill"


def test_route_prompt_detects_document_intent() -> None:
    route = route_prompt("Extract invoice fields from this PDF")

    assert route.category == "document"
    assert route.tool_name == "resolve_document_processing_flow"


def test_route_prompt_rejects_blank_prompt() -> None:
    with pytest.raises(ToolError, match="prompt must not be empty"):
        route_prompt("   ")


@pytest.mark.anyio
async def test_execute_prompt_tool_calls_inferred_backend_tool() -> None:
    response = await execute_prompt_tool(
        PromptExecutionRequest(prompt="Build Node API with Express and TypeScript")
    )

    assert response.tool_name == "resolve_backend_skill"
    assert response.result["stack"] == "node_express_typescript"


@pytest.mark.anyio
async def test_execute_prompt_tool_calls_explicit_document_tool() -> None:
    response = await execute_prompt_tool(
        PromptExecutionRequest(
            prompt="I need redaction support",
            tool_name="generate_document_tool_spec",
            arguments={"capability": "redact"},
        )
    )

    assert response.tool_name == "generate_document_tool_spec"
    assert response.result["name"] == "redact_document"


def test_get_prompt_route_endpoint() -> None:
    client = TestClient(create_app())

    response = client.get("/api/prompts/route", params={"prompt": "Need a Java backend"})

    assert response.status_code == 200
    assert response.json()["tool_name"] == "resolve_backend_skill"


def test_post_prompt_execute_endpoint() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/prompts/execute",
        json={"prompt": "Process a resume document"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool_name"] == "resolve_document_processing_flow"
    assert payload["result"]["document_type"] == "curriculum vitae"


def test_docs_endpoint_serves_swagger_ui() -> None:
    client = TestClient(create_app())

    response = client.get("/docs")

    assert response.status_code == 200
    assert "SwaggerUIBundle" in response.text
    assert "/openapi.json" in response.text


def test_openapi_schema_documents_prompt_routes() -> None:
    client = TestClient(create_app())

    response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    assert schema["openapi"].startswith("3.")
    assert "/api/prompts/route" in schema["paths"]
    assert "/api/prompts/execute" in schema["paths"]
    assert "PromptExecutionRequest" in schema["components"]["schemas"]


def test_http_dependency_checker_reports_missing_modules() -> None:
    from http_api import get_missing_http_dependencies

    assert get_missing_http_dependencies(("missing_smart_ide_http_dependency",)) == (
        "missing_smart_ide_http_dependency",
    )


@pytest.mark.anyio
async def test_missing_dependency_asgi_returns_setup_guidance() -> None:
    from http_api import MissingDependencyASGI

    sent_messages = []

    async def receive() -> dict[str, str]:
        return {"type": "http.request"}

    async def send(message: dict[str, object]) -> None:
        sent_messages.append(message)

    app = MissingDependencyASGI(("starlette",))

    await app({"type": "http"}, receive, send)

    assert sent_messages[0]["status"] == 503
    assert b"python -m pip install -e ." in sent_messages[1]["body"]
