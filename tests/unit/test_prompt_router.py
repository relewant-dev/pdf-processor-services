from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastmcp.exceptions import ToolError
from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from http_api import create_app
from services.prompt_router import (
    PromptExecutionRequest,
    execute_prompt_tool,
    route_prompt,
)


def test_route_prompt_detects_backend_intent() -> None:
    route = route_prompt("Create a Python FastAPI backend")

    assert route.category == "backend"
    assert route.tool_name == "resolve_backend_skill"


def test_route_prompt_detects_document_intent() -> None:
    route = route_prompt("Extract invoice fields from this PDF")

    assert route.category == "document"
    assert route.tool_name == "resolve_document_processing_flow"


def test_route_prompt_detects_insurance_intent() -> None:
    route = route_prompt("Read this insurance policy and explain coverage")

    assert route.category == "document"
    assert route.tool_name == "resolve_document_processing_flow"


def test_route_prompt_detects_cv_reading_intent() -> None:
    route = route_prompt("Read this CV and summarize the candidate profile")

    assert route.category == "document"
    assert route.tool_name == "resolve_document_processing_flow"


def test_route_prompt_rejects_blank_prompt() -> None:
    with pytest.raises(ToolError, match="message must not be empty"):
        route_prompt("   ")


@pytest.mark.anyio
async def test_execute_prompt_tool_calls_inferred_backend_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_prompts: list[str] = []

    async def fake_chat_with_ollama(prompt: str) -> str:
        captured_prompts.append(prompt)
        return "generated backend result"

    monkeypatch.setattr(
        "services.prompt_router.chat_with_ollama", fake_chat_with_ollama
    )

    response = await execute_prompt_tool(
        PromptExecutionRequest(message="Build Node API with Express and TypeScript")
    )

    assert response.response == "generated backend result"
    assert len(captured_prompts) == 1
    assert "resolve_backend_skill" in captured_prompts[0]
    assert "node_express_typescript" in captured_prompts[0]
    assert "generate-express-typescript-backend" in captured_prompts[0]


@pytest.mark.anyio
async def test_execute_prompt_tool_accepts_frontend_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_prompts: list[str] = []

    async def fake_chat_with_ollama(prompt: str) -> str:
        captured_prompts.append(prompt)
        return "document result"

    monkeypatch.setattr(
        "services.prompt_router.chat_with_ollama", fake_chat_with_ollama
    )

    response = await execute_prompt_tool(
        PromptExecutionRequest.model_validate(
            {"message": "I need redaction support for a document"}
        )
    )

    assert response.response == "document result"
    assert "resolve_document_processing_flow" in captured_prompts[0]
    assert "generic_structured_extraction" in captured_prompts[0]


@pytest.mark.anyio
async def test_execute_prompt_tool_routes_cv_reading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_prompts: list[str] = []

    async def fake_chat_with_ollama(prompt: str) -> str:
        captured_prompts.append(prompt)
        return "cv result"

    monkeypatch.setattr(
        "services.prompt_router.chat_with_ollama", fake_chat_with_ollama
    )

    response = await execute_prompt_tool(
        PromptExecutionRequest(message="Read this CV and extract skills")
    )

    assert response.response == "cv result"
    assert "resolve_document_processing_flow" in captured_prompts[0]
    assert "cv_reading" in captured_prompts[0]
    assert "cv-reader-agent" in captured_prompts[0]
    assert "cv-reading" in captured_prompts[0]


@pytest.mark.anyio
async def test_execute_prompt_tool_routes_insurance_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_prompts: list[str] = []

    async def fake_chat_with_ollama(prompt: str) -> str:
        captured_prompts.append(prompt)
        return "insurance result"

    monkeypatch.setattr(
        "services.prompt_router.chat_with_ollama", fake_chat_with_ollama
    )

    response = await execute_prompt_tool(
        PromptExecutionRequest(
            message="Read this insurance policy for claim requirements"
        )
    )

    assert response.response == "insurance result"
    assert "resolve_document_processing_flow" in captured_prompts[0]
    assert "insurance_policy_reading" in captured_prompts[0]
    assert "insurance policy" in captured_prompts[0]


def test_get_prompt_route_endpoint_is_removed() -> None:
    client = TestClient(create_app())

    response = client.get(
        "/api/prompts/route", params={"prompt": "Need a Java backend"}
    )

    assert response.status_code == 404


def test_post_prompt_execute_endpoint_returns_only_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_chat_with_ollama(_: str) -> str:
        return "Process the resume with structured extraction."

    monkeypatch.setattr(
        "services.prompt_router.chat_with_ollama", fake_chat_with_ollama
    )
    client = TestClient(create_app())

    response = client.post(
        "/api/prompts/execute",
        json={"message": "Process a resume document"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "response": "Process the resume with structured extraction."
    }


def test_post_prompt_execute_rejects_extra_fields() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/prompts/execute",
        json={"message": "Process a resume document", "arguments": {}},
    )

    assert response.status_code == 422


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
    assert "/api/prompts/route" not in schema["paths"]
    assert "/api/prompts/execute" in schema["paths"]
    assert "PromptExecutionRequest" in schema["components"]["schemas"]
    assert schema["components"]["schemas"]["PromptExecutionRequest"][
        "properties"
    ].keys() == {"message"}


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
