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

    async def fake_chat_with_ollama(prompt: str, **kwargs: object) -> str:
        captured["prompt"] = prompt
        captured["response_format"] = str(kwargs.get("response_format"))
        captured["options"] = str(kwargs.get("options"))
        return '{"anagraphical_data":["Gabriele","Lugano"],"experience":["Senior Developer"],"education":["Not specified"],"skills":["Not specified"],"certifications":["Not specified"],"hobby":["Not specified"]}'

    monkeypatch.setattr(cv_anonymization, "chat_with_ollama", fake_chat_with_ollama)

    result = asyncio.run(
        cv_anonymization.anonymize_cv_text(
            "Gabriele Di Somma\ngabriele@example.com\nVia Roma 10, Lugano"
        )
    )

    assert result == (
        "**Anagraphical data**\n"
        "• Gabriele\n"
        "• Lugano\n\n"
        "**Experience**\n"
        "• Senior Developer"
    )
    assert "Keep only the candidate first/given name" in captured["prompt"]
    assert "Remove phone numbers" in captured["prompt"]
    assert "Remove email addresses" in captured["prompt"]
    assert "Remove street addresses" in captured["prompt"]
    assert "Remove house numbers" in captured["prompt"]
    assert "Remove postal codes" in captured["prompt"]
    assert "Keep only the city" in captured["prompt"]
    assert "anagraphical_data" in captured["prompt"]
    assert "experience" in captured["prompt"]
    assert "education" in captured["prompt"]
    assert "skills" in captured["prompt"]
    assert "certifications" in captured["prompt"]
    assert "hobby" in captured["prompt"]
    assert "Return only valid JSON" in captured["prompt"]
    assert "Classify all remaining CV information" in captured["prompt"]
    assert "Do not summarize professional content" in captured["prompt"]
    assert "response_format" in captured
    assert "temperature" in captured["options"]


def test_remove_introductory_sentence_helper_removes_legacy_intro() -> None:
    result = cv_anonymization._remove_introductory_sentence(
        "Here is the anonymized CV content for PDF export:\nLugano\nSenior Developer"
    )

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


def test_pdf_line_style_renders_markdown_heading_as_real_bold_text() -> None:
    font_name, line = cv_pdf_rendering._pdf_line_style("**Experience**", "Helvetica", "Helvetica-Bold")

    assert font_name == "Helvetica-Bold"
    assert line == "Experience"


def test_render_anonymized_cv_pdf_one_page_cv_is_rendered_once(tmp_path: Path) -> None:
    from pypdf import PdfReader

    output_path = tmp_path / "anonymized-cv.pdf"
    text = (
        "Here is the anonymized CV content for PDF export:\n"
        "**Anagraphical data**\n"
        "• Gabriele\n"
        "• Lugano\n"
        "**Experience**\n"
        "• Senior Developer\n"
        "**Education**\n"
        "• University\n"
        "**Skills**\n"
        "• Python\n"
        "**Certifications**\n"
        "• Not specified\n"
        "**Hobby**\n"
        "• Reading"
    )
    cleaned_text = cv_anonymization._remove_introductory_sentence(text)

    cv_pdf_rendering.render_anonymized_cv_pdf(cleaned_text, output_path)

    reader = PdfReader(str(output_path))
    page_texts = [page.extract_text() or "" for page in reader.pages]
    full_text = "\n".join(page_texts)

    assert len(page_texts) == 1
    assert "Here is the anonymized CV content for PDF export:" not in full_text
    assert full_text.count("Anagraphical data") == 1
    assert full_text.count("Experience") == 1
    assert full_text.count("Senior Developer") == 1
    assert full_text.count("Skills") == 1


def test_anonymized_cv_endpoint_anonymizes_once_and_renders_once(monkeypatch: pytest.MonkeyPatch) -> None:
    from starlette.applications import Starlette
    from starlette.testclient import TestClient

    from routers import cv_export as cv_export_router

    calls: dict[str, int] = {"extract": 0, "anonymize": 0, "render": 0}

    async def fake_extract(upload: UploadFile) -> str:
        calls["extract"] += 1
        return "Raw one-page CV"

    async def fake_anonymize(text: str) -> str:
        calls["anonymize"] += 1
        assert text == "Raw one-page CV"
        return "**Experience**\n• Developer"

    def fake_render(text: str, output_path: Path) -> Path:
        calls["render"] += 1
        assert text == "**Experience**\n• Developer"
        output_path.write_bytes(b"%PDF anonymized once")
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
    assert response.content == b"%PDF anonymized once"
    assert calls == {"extract": 1, "anonymize": 1, "render": 1}

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


def test_cv_flow_lines_add_spacing_only_between_sections() -> None:
    text = (
        "**Experience**\n"
        "\n"
        "• Senior Developer\n"
        "\n"
        "• Platform Engineer\n"
        "\n"
        "**Skills**\n"
        "\n"
        "• Python\n"
        "• FastMCP\n"
        "\n"
        "**Certifications**\n"
        "• Cloud Practitioner — 2024 — Provider\n"
        "• Built secure services"
    )

    flow_lines = cv_pdf_rendering._build_cv_flow_lines(text)

    assert [line.text for line in flow_lines] == [
        "**Experience**",
        "• Senior Developer",
        "• Platform Engineer",
        "**Skills**",
        "• Python",
        "• FastMCP",
        "**Certifications**",
        "• Cloud Practitioner — 2024 — Provider",
        "• Built secure services",
    ]
    assert [line.starts_section for line in flow_lines] == [
        False,
        False,
        False,
        True,
        False,
        False,
        True,
        False,
        False,
    ]


def test_cv_flow_lines_normalize_square_bullets_to_round_bullets() -> None:
    text = (
        "**Experience**\n"
        "▪ Senior Developer\n"
        "■ Platform Engineer\n"
        "□ Team Lead"
    )

    flow_lines = cv_pdf_rendering._build_cv_flow_lines(text)

    assert [line.text for line in flow_lines] == [
        "**Experience**",
        "• Senior Developer",
        "• Platform Engineer",
        "• Team Lead",
    ]


def test_round_bullet_text_detects_only_round_bullet_prefixes() -> None:
    assert cv_pdf_rendering._round_bullet_text("• Senior Developer") == "Senior Developer"
    assert cv_pdf_rendering._round_bullet_text("  • Lugano") == "Lugano"
    assert cv_pdf_rendering._round_bullet_text("Experience") is None


def test_write_text_overlay_single_page_does_not_duplicate_content(tmp_path: Path) -> None:
    from pypdf import PdfReader

    overlay_path = tmp_path / "single-page-overlay.pdf"
    text = (
        "**Anagraphical data**\n"
        "• Candidate\n"
        "**Experience**\n"
        "• Developer\n"
        "**Education**\n"
        "• University\n"
        "**Skills**\n"
        "• Python\n"
        "• PDF rendering\n"
        "**Certifications**\n"
        "• Cloud Practitioner — 2024 — Example Provider\n"
        "• Validated cloud fundamentals\n"
        "**Hobby**\n"
        "• Reading"
    )

    cv_pdf_rendering._write_text_overlay(text, overlay_path, 595, 842)

    reader = PdfReader(str(overlay_path))
    extracted_pages = [page.extract_text() for page in reader.pages]
    full_text = "\n".join(extracted_pages)
    assert len(extracted_pages) == 1
    assert full_text.count("Skills") == 1
    assert full_text.count("Certifications") == 1
    assert full_text.index("Skills") < full_text.index("Certifications")
    assert full_text.count("Cloud Practitioner") == 1


def test_write_text_overlay_multipage_continues_instead_of_repeating_page_one(tmp_path: Path) -> None:
    from pypdf import PdfReader

    overlay_path = tmp_path / "multipage-overlay.pdf"
    experience_items = "\n".join(f"• Experience item {index}" for index in range(1, 80))
    text = (
        "**Experience**\n"
        f"{experience_items}\n"
        "**Skills**\n"
        "• Python\n"
        "**Certifications**\n"
        "• Cloud Practitioner — 2024 — Example Provider\n"
        "• Validated cloud fundamentals"
    )

    cv_pdf_rendering._write_text_overlay(text, overlay_path, 595, 842)

    reader = PdfReader(str(overlay_path))
    extracted_pages = [page.extract_text() for page in reader.pages]
    assert len(extracted_pages) > 1
    assert extracted_pages[0] != extracted_pages[1]
    combined_text = "\n".join(extracted_pages)
    assert combined_text.splitlines().count("Experience") == 1
    assert combined_text.count("Experience item 79") == 1
    assert combined_text.count("Skills") == 1
    assert combined_text.count("Certifications") == 1
    assert combined_text.index("Skills") < combined_text.index("Certifications")


def test_cv_json_with_experience_must_not_return_not_specified() -> None:
    response = '{"anagraphical_data":["Gabriele"],"experience":["Not specified"],"education":["Not specified"],"skills":["Not specified"],"certifications":["Not specified"],"hobby":["Not specified"]}'

    with pytest.raises(ToolError, match="omitted source experience"):
        cv_anonymization._parse_and_validate_cv_json(response, "Experience: Senior Developer at Example")


def test_cv_json_with_skills_must_not_return_not_specified() -> None:
    response = '{"anagraphical_data":["Gabriele"],"experience":["Not specified"],"education":["Not specified"],"skills":["Not specified"],"certifications":["Not specified"],"hobby":["Not specified"]}'

    with pytest.raises(ToolError, match="omitted source skills"):
        cv_anonymization._parse_and_validate_cv_json(response, "Skills: Python, Docker, SQL")


def test_cv_json_with_education_must_not_return_not_specified() -> None:
    response = '{"anagraphical_data":["Gabriele"],"experience":["Not specified"],"education":["Not specified"],"skills":["Not specified"],"certifications":["Not specified"],"hobby":["Not specified"]}'

    with pytest.raises(ToolError, match="omitted source education"):
        cv_anonymization._parse_and_validate_cv_json(response, "Education: Bachelor degree at University")


def test_anonymize_cv_text_formats_valid_json_and_omits_missing_sections(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_chat_with_ollama(prompt: str, **kwargs: object) -> str:
        assert kwargs["response_format"] == cv_anonymization.OLLAMA_JSON_FORMAT
        assert kwargs["options"] == {"temperature": 0}
        return '{"anagraphical_data":["Gabriele","Lugano"],"experience":["Senior Developer"],"education":["University"],"skills":["Python"],"certifications":["Not specified"],"hobby":["Not specified"]}'

    monkeypatch.setattr(cv_anonymization, "chat_with_ollama", fake_chat_with_ollama)

    result = asyncio.run(cv_anonymization.anonymize_cv_text("Experience: Senior Developer\nEducation: University\nSkills: Python"))

    for section in ("Anagraphical data", "Experience", "Education", "Skills"):
        assert result.count(f"**{section}**") == 1
    assert "**Certifications**" not in result
    assert "**Hobby**" not in result
    assert "• Not specified" not in result
    assert "• Senior Developer" in result


def test_anonymize_cv_text_allows_omitted_and_empty_missing_sections(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_chat_with_ollama(prompt: str, **_: object) -> str:
        return '{"anagraphical_data":["Gabriele"],"experience":["Developer"],"hobby":[]}'

    monkeypatch.setattr(cv_anonymization, "chat_with_ollama", fake_chat_with_ollama)

    result = asyncio.run(cv_anonymization.anonymize_cv_text("Gabriele\nExperience: Developer"))

    assert "**Anagraphical data**" in result
    assert "**Experience**" in result
    assert "**Education**" not in result
    assert "**Skills**" not in result
    assert "**Certifications**" not in result
    assert "**Hobby**" not in result


def test_anonymize_cv_text_retries_once_with_repair_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = iter([
        "not json",
        '{"anagraphical_data":["Gabriele"],"experience":["Developer"],"education":["Not specified"],"skills":["Python"],"certifications":["Not specified"],"hobby":["Not specified"]}',
    ])
    prompts: list[str] = []

    async def fake_chat_with_ollama(prompt: str, **_: object) -> str:
        prompts.append(prompt)
        return next(responses)

    monkeypatch.setattr(cv_anonymization, "chat_with_ollama", fake_chat_with_ollama)

    result = asyncio.run(cv_anonymization.anonymize_cv_text("Experience: Developer\nSkills: Python"))

    assert "Repair this anonymized CV response" in prompts[1]
    assert result.count("**Experience**") == 1


def test_deduplicate_overlay_pages_compares_normalized_text() -> None:
    class Page:
        def __init__(self, text: str) -> None:
            self.text = text

        def extract_text(self) -> str:
            return self.text

    first = Page("Experience\nDeveloper")
    duplicate = Page("  Experience   Developer  ")
    second = Page("Skills\nPython")

    assert cv_pdf_rendering._deduplicate_overlay_pages([first, duplicate, second]) == [first, second]


def test_rendered_pdf_does_not_contain_duplicated_content_pages(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    template_path = tmp_path / "template.pdf"
    template_path.write_bytes(b"template")
    output_path = tmp_path / "out.pdf"

    class FakePage:
        mediabox = SimpleNamespace(width=595, height=842)

        def __init__(self, text: str = "") -> None:
            self.text = text

        def extract_text(self) -> str:
            return self.text

        def merge_page(self, other: object) -> None:
            self.text = other.extract_text()

    class FakeReader:
        def __init__(self, path: str) -> None:
            if path.endswith("overlay.pdf"):
                self.pages = [FakePage("Experience\nDeveloper"), FakePage(" Experience Developer ")]
            else:
                self.pages = [FakePage("Template")]

    class FakeWriter:
        def __init__(self) -> None:
            self.pages: list[FakePage] = []

        def add_page(self, page: FakePage) -> None:
            self.pages.append(page)

        def write(self, file_obj: object) -> None:
            file_obj.write(str(len(self.pages)).encode())

    import sys

    monkeypatch.setitem(sys.modules, "pypdf", SimpleNamespace(PdfReader=FakeReader, PdfWriter=FakeWriter))
    monkeypatch.setattr(cv_pdf_rendering, "_write_text_overlay", lambda text, overlay_path, width, height: overlay_path.write_bytes(b"overlay"))

    cv_pdf_rendering.render_anonymized_cv_pdf("**Experience**\n• Developer", output_path, template_path=template_path)

    assert output_path.read_bytes() == b"1"
