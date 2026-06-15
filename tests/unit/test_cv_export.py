import asyncio
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastmcp.exceptions import ToolError
from starlette.datastructures import Headers, UploadFile

from services import cv_anonymization, cv_extraction, cv_pdf_rendering


def make_upload(
    filename: str = "cv.pdf",
    content_type: str = "application/pdf",
    content: bytes = b"%PDF-1.7",
) -> UploadFile:
    return UploadFile(
        BytesIO(content),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


def test_extract_cv_text_from_upload_writes_pdf_and_extracts_text(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_extract_pdf_text(file_path: str) -> str:
        captured["file_path"] = file_path
        captured["exists_during_extraction"] = Path(file_path).is_file()
        return "Gabriele Di Somma\nSenior Developer"

    monkeypatch.setattr(cv_extraction, "extract_pdf_text", fake_extract_pdf_text)

    result = asyncio.run(cv_extraction.extract_cv_text_from_upload(make_upload()))

    assert result == "Gabriele Di Somma\nSenior Developer"
    assert captured["file_path"].endswith("cv-upload.pdf")
    assert captured["exists_during_extraction"] is True


def test_extract_cv_text_from_upload_rejects_invalid_pdf() -> None:
    with pytest.raises(ToolError, match=".pdf filename"):
        asyncio.run(cv_extraction.extract_cv_text_from_upload(make_upload(filename="cv.txt", content_type="text/plain")))


def test_anonymize_cv_text_uses_ollama_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str] = {}

    async def fake_chat_with_ollama(prompt: str, **_: object) -> str:
        captured["prompt"] = prompt
        return "Lugano\nSenior Developer"

    monkeypatch.setattr(cv_anonymization, "chat_with_ollama", fake_chat_with_ollama)

    result = asyncio.run(cv_anonymization.anonymize_cv_text("Gabriele Di Somma\ngabriele@example.com\nVia Roma 10, Lugano"))

    assert result == "Lugano\nSenior Developer"
    assert "Remove phone numbers" in captured["prompt"]
    assert "Remove email addresses" in captured["prompt"]
    assert "Remove the candidate's first name and surname completely" in captured["prompt"]
    assert "do not leave, replace, initialize, or pseudonymize" in captured["prompt"]
    assert "Return only the anonymized CV content" in captured["prompt"]
    assert "The response must start directly with the CV content" in captured["prompt"]
    assert "Do not include any introductory text" in captured["prompt"]
    assert "Here is the anonymized CV content for PDF export" not in captured["prompt"]


def test_anonymize_cv_text_removes_introductory_sentence(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_chat_with_ollama(prompt: str, **_: object) -> str:
        return "Here is the anonymized CV content for PDF export:\nLugano\nSenior Developer"

    monkeypatch.setattr(cv_anonymization, "chat_with_ollama", fake_chat_with_ollama)

    result = asyncio.run(cv_anonymization.anonymize_cv_text("Gabriele Di Somma"))

    assert result == "Lugano\nSenior Developer"


def test_anonymize_cv_text_rejects_empty_ollama_response(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_chat_with_ollama(prompt: str, **_: object) -> str:
        return "   "

    monkeypatch.setattr(cv_anonymization, "chat_with_ollama", fake_chat_with_ollama)

    with pytest.raises(ToolError, match="empty anonymized CV response"):
        asyncio.run(cv_anonymization.anonymize_cv_text("CV text"))


def test_render_anonymized_cv_pdf_requires_template(tmp_path: Path) -> None:
    with pytest.raises(ToolError, match="template not found"):
        cv_pdf_rendering.render_anonymized_cv_pdf(
            "M. R.\nEngineer",
            tmp_path / "out.pdf",
            template_path=tmp_path / "missing-template.pdf",
        )


def test_render_anonymized_cv_pdf_writes_output_with_template(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    template_path = tmp_path / "template.pdf"
    template_path.write_bytes(b"template")
    output_path = tmp_path / "out.pdf"

    class FakePage:
        mediabox = SimpleNamespace(width=595, height=842)

        def merge_page(self, other: object) -> None:
            self.other = other

    class FakeReader:
        def __init__(self, path: str) -> None:
            self.pages = [FakePage()]

    class FakeWriter:
        def __init__(self) -> None:
            self.pages = []

        def add_page(self, page: object) -> None:
            self.pages.append(page)

        def write(self, file_obj: object) -> None:
            file_obj.write(b"%PDF fake anonymized cv")

    import sys

    monkeypatch.setitem(sys.modules, "pypdf", SimpleNamespace(PdfReader=FakeReader, PdfWriter=FakeWriter))
    monkeypatch.setattr(cv_pdf_rendering, "_write_text_overlay", lambda text, overlay_path, width, height: overlay_path.write_bytes(b"overlay"))

    result = cv_pdf_rendering.render_anonymized_cv_pdf("M. R.\nEngineer", output_path, template_path=template_path)

    assert result == output_path
    assert output_path.read_bytes() == b"%PDF fake anonymized cv"
    assert not output_path.with_suffix(".overlay.pdf").exists()


def test_anonymized_cv_endpoint_returns_pdf_and_deletes_temp_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    from starlette.applications import Starlette
    from starlette.testclient import TestClient

    from routers import cv_export as cv_export_router

    captured: dict[str, object] = {}

    async def fake_extract(upload: UploadFile) -> str:
        captured["filename"] = upload.filename
        return "Raw CV"

    async def fake_anonymize(text: str) -> str:
        captured["text"] = text
        return "Anonymized CV"

    def fake_render(text: str, output_path: Path) -> Path:
        captured["anonymized"] = text
        output_path.write_bytes(b"%PDF anonymized")
        captured["temp_dir"] = output_path.parent
        return output_path

    monkeypatch.setattr(cv_export_router, "extract_cv_text_from_upload", fake_extract)
    monkeypatch.setattr(cv_export_router, "anonymize_cv_text", fake_anonymize)
    monkeypatch.setattr(cv_export_router, "render_anonymized_cv_pdf", fake_render)

    client = TestClient(Starlette(routes=cv_export_router.router.routes))
    response = client.post(
        "/api/cv/anonymized-pdf",
        files={"file": ("cv.pdf", b"%PDF-1.7", "application/pdf")},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content == b"%PDF anonymized"
    assert captured["filename"] == "cv.pdf"
    assert captured["text"] == "Raw CV"
    assert captured["anonymized"] == "Anonymized CV"
    assert not captured["temp_dir"].exists()
