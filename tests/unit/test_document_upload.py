import asyncio
from io import BytesIO

import pytest
from fastmcp.exceptions import ToolError
from starlette.datastructures import Headers, UploadFile

from services import document_upload
from services.document_upload import PdfUploadRequest, process_pdf_upload


def make_upload(
    filename: str = "sample.pdf",
    content_type: str = "application/pdf",
    content: bytes = b"%PDF-1.7",
) -> UploadFile:
    return UploadFile(
        BytesIO(content),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


def test_process_pdf_upload_extracts_uploaded_pdf_and_calls_ollama(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str] = {}

    def fake_extract_pdf_text(file_path: str) -> str:
        captured["file_path"] = file_path
        return "Uploaded PDF text"

    async def fake_chat_with_ollama(prompt: str) -> str:
        captured["prompt"] = prompt
        return "PDF answer"

    monkeypatch.setattr(document_upload, "extract_pdf_text", fake_extract_pdf_text)
    monkeypatch.setattr(document_upload, "chat_with_ollama", fake_chat_with_ollama)

    response = asyncio.run(
        process_pdf_upload(
            make_upload(),
            PdfUploadRequest(question="What is this document?", max_chars=1000),
        )
    )

    assert response.response == "PDF answer"
    assert captured["file_path"].endswith(".pdf")
    assert "Uploaded PDF text" in captured["prompt"]
    assert "What is this document?" in captured["prompt"]


def test_process_pdf_upload_rejects_non_pdf_filename() -> None:
    with pytest.raises(ToolError, match=".pdf filename"):
        asyncio.run(
            process_pdf_upload(
                make_upload(filename="notes.txt", content_type="text/plain"),
                PdfUploadRequest(question="What is this?"),
            )
        )


def test_process_pdf_upload_rejects_empty_upload() -> None:
    with pytest.raises(ToolError, match="empty"):
        asyncio.run(
            process_pdf_upload(
                make_upload(content=b""),
                PdfUploadRequest(question="What is this?"),
            )
        )


def test_pdf_upload_endpoint_accepts_multipart_form_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from starlette.applications import Starlette
    from starlette.testclient import TestClient

    from routers import document as document_router
    from services.document_upload import PdfUploadResponse

    captured: dict[str, object] = {}

    async def fake_process_pdf_upload(
        upload: UploadFile,
        request: PdfUploadRequest,
    ) -> PdfUploadResponse:
        captured["filename"] = upload.filename
        captured["question"] = request.question
        captured["max_chars"] = request.max_chars
        return PdfUploadResponse(response="endpoint answer")

    monkeypatch.setattr(document_router, "process_pdf_upload", fake_process_pdf_upload)
    client = TestClient(Starlette(routes=document_router.router.routes))

    response = client.post(
        "/api/documents/pdf",
        data={"question": "Summarize", "max_chars": "123"},
        files={"file": ("sample.pdf", b"%PDF-1.7", "application/pdf")},
    )

    assert response.status_code == 200
    assert response.json() == {"response": "endpoint answer"}
    assert captured == {
        "filename": "sample.pdf",
        "question": "Summarize",
        "max_chars": 123,
    }


def test_pdf_upload_openapi_documents_text_extraction_before_ollama() -> None:
    from http_api import build_openapi_schema

    operation = build_openapi_schema()["paths"]["/api/documents/pdf"]["post"]

    assert "extracted text" in operation["summary"]
    assert "Ollama does not receive or parse raw PDF bytes" in operation["description"]
