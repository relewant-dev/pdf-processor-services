import asyncio
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastmcp.exceptions import ToolError
from starlette.datastructures import Headers, UploadFile

from services import cv_anonymization, cv_extraction, cv_pdf_rendering


EXPECTED_SECTION_HEADINGS = [
    "**Personal data**",
    "**Experience**",
    "**Education**",
    "**Skills**",
    "**Certifications**",
    "**Hobby**",
]


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
        return "Gabriele\nSenior Developer"

    monkeypatch.setattr(cv_extraction, "extract_pdf_text", fake_extract_pdf_text)

    result = asyncio.run(cv_extraction.extract_cv_text_from_upload(make_upload()))

    assert result == "Gabriele\nSenior Developer"
    assert captured["file_path"].endswith("cv-upload.pdf")
    assert captured["exists_during_extraction"] is True


def test_extract_cv_text_from_upload_rejects_invalid_pdf() -> None:
    with pytest.raises(ToolError, match=".pdf filename"):
        asyncio.run(cv_extraction.extract_cv_text_from_upload(make_upload(filename="cv.txt", content_type="text/plain")))


def test_anonymize_cv_text_uses_ollama_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str] = {}

    async def fake_chat_with_ollama(prompt: str, **_: object) -> str:
        captured["prompt"] = prompt
        return (
            "**Personal data**\n"
            "• Gabriele\n"
            "• Lugano\n"
            "**Experience**\n"
            "• Senior Developer\n"
            "**Education**\n"
            "• Not specified\n"
            "**Skills**\n"
            "• Not specified\n"
            "**Certifications**\n"
            "• Not specified\n"
            "**Hobby**\n"
            "• Not specified"
        )

    monkeypatch.setattr(cv_anonymization, "chat_with_ollama", fake_chat_with_ollama)

    result = asyncio.run(
        cv_anonymization.anonymize_cv_text(
            "Gabriele\ngabriele@example.com\nVia Roma 10, Lugano"
        )
    )

    assert result == (
        "**Personal data**\n"
        "• Gabriele\n"
        "• Lugano\n"
        "\n"
        "**Experience**\n"
        "• Senior Developer\n"
        "\n"
        "**Education**\n"
        "• Not specified\n"
        "\n"
        "**Skills**\n"
        "• Not specified\n"
        "\n"
        "**Certifications**\n"
        "• Not specified\n"
        "\n"
        "**Hobby**\n"
        "• Not specified"
    )
    assert "Keep only the given first name" in captured["prompt"]
    assert "Remove email, phone number" in captured["prompt"]
    assert "street address, street name, house number, and postal code" in captured["prompt"]
    assert "Keep city only from addresses" in captured["prompt"]
    assert "Personal data" in captured["prompt"]
    assert "Experience" in captured["prompt"]
    assert "Education" in captured["prompt"]
    assert "Skills" in captured["prompt"]
    assert "Certifications" in captured["prompt"]
    assert "Hobby" in captured["prompt"]
    assert "Section titles must be bold in the exported PDF" in captured["prompt"]
    assert "Use only round bullet points" in captured["prompt"]
    assert "never use square bullet points" in captured["prompt"]
    assert "Return only the formatted anonymized CV" in captured["prompt"]
    assert "Your task is NOT to summarize" in captured["prompt"]
    assert "Your task is NOT to shorten" in captured["prompt"]
    assert "Your task is NOT to evaluate relevance" in captured["prompt"]
    assert "Your task is NOT to remove professional content" in captured["prompt"]
    assert "Do not compress multiple bullet points into one" in captured["prompt"]
    assert "Do not remove company names, client names, roles, projects" in captured["prompt"]
    assert "Never write explanations, notes, or comments" in captured["prompt"]


def test_anonymize_cv_text_preserves_professional_entries_and_detail(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_chat_with_ollama(prompt: str, **_: object) -> str:
        assert "Senior Developer at ExampleBank" in prompt
        assert "Teaching Assistant at Example University" in prompt
        return (
            "**Personal data**\n"
            "• Lugano\n"
            "**Experience**\n"
            "• Senior Developer at ExampleBank — 2021-2024\n"
            "• Built payment APIs with Python, FastAPI, PostgreSQL, Docker, and Kubernetes.\n"
            "• Led migration of legacy batch jobs to asynchronous services and reduced processing time.\n"
            "• Teaching Assistant at Example University — 2019-2020\n"
            "• Delivered Python labs, reviewed assignments, and supported student projects.\n"
            "**Education**\n"
            "• MSc Computer Science — Example University — 2020\n"
            "**Skills**\n"
            "• Core Competencies: architecture, mentoring, stakeholder management\n"
            "• Technical Skills: Python, FastAPI, PostgreSQL, Docker, Kubernetes\n"
            "• Stack: Linux, Git, CI/CD, REST APIs\n"
            "**Certifications**\n"
            "• Not specified\n"
            "**Hobby**\n"
            "• Not specified"
        )

    monkeypatch.setattr(cv_anonymization, "chat_with_ollama", fake_chat_with_ollama)

    result = asyncio.run(
        cv_anonymization.anonymize_cv_text(
            "Mario Rossi\n"
            "Senior Developer at ExampleBank — 2021-2024\n"
            "Built payment APIs with Python, FastAPI, PostgreSQL, Docker, and Kubernetes.\n"
            "Led migration of legacy batch jobs to asynchronous services and reduced processing time.\n"
            "Teaching Assistant at Example University — 2019-2020\n"
            "Delivered Python labs, reviewed assignments, and supported student projects.\n"
            "MSc Computer Science — Example University — 2020\n"
            "Core Competencies: architecture, mentoring, stakeholder management\n"
            "Technical Skills: Python, FastAPI, PostgreSQL, Docker, Kubernetes\n"
            "Stack: Linux, Git, CI/CD, REST APIs"
        )
    )

    assert "Senior Developer at ExampleBank" in result
    assert "Teaching Assistant at Example University" in result
    assert "Built payment APIs with Python, FastAPI, PostgreSQL, Docker, and Kubernetes." in result
    assert "Led migration of legacy batch jobs to asynchronous services and reduced processing time." in result
    assert "Delivered Python labs, reviewed assignments, and supported student projects." in result
    assert "Core Competencies: architecture, mentoring, stakeholder management" in result
    assert "Technical Skills: Python, FastAPI, PostgreSQL, Docker, Kubernetes" in result
    assert "Stack: Linux, Git, CI/CD, REST APIs" in result
    assert "removed this section because" not in result.lower()
    for heading in EXPECTED_SECTION_HEADINGS:
        assert result.count(heading) == 1


def test_anonymize_cv_text_uses_deterministic_full_cv_ollama_options(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    async def fake_chat_with_ollama(prompt: str, **kwargs: object) -> str:
        captured["prompt"] = prompt
        captured["options"] = kwargs.get("options")
        return (
            "**Personal data**\n• Candidate\n"
            "**Experience**\n• Professional Experience: Senior Java Engineer at ExampleBank\n"
            "**Education**\n• Education: MSc Computer Science\n"
            "**Skills**\n• Technical Skills: Java, Spring Boot, Python, Docker, AWS, Kafka, React, SQL, Kubernetes, GitLab CI/CD, Agile/SAFe\n"
            "**Certifications**\n• Not specified\n"
            "**Hobby**\n• Not specified"
        )

    monkeypatch.setattr(cv_anonymization, "chat_with_ollama", fake_chat_with_ollama)

    source_cv = (
        "Page 1\nProfessional Experience\nSenior Java Engineer at ExampleBank\n"
        "Built Spring Boot services with Kafka and SQL.\n"
        "Page 2\nTechnical Skills\nJava, Spring Boot, Python, Docker, AWS, Kafka, React, SQL, Kubernetes, GitLab CI/CD, Agile/SAFe\n"
        "Education\nMSc Computer Science"
    )

    result = asyncio.run(cv_anonymization.anonymize_cv_text(source_cv))

    assert "Professional Experience" in captured["prompt"]
    assert "Technical Skills" in captured["prompt"]
    assert "Education" in captured["prompt"]
    assert captured["options"] == {"temperature": 0, "num_ctx": 32768, "num_predict": 12000}
    assert "Experience: Not specified" not in result
    assert "Skills: Not specified" not in result


def test_anonymize_cv_text_repairs_omitted_experience_and_skills(monkeypatch: pytest.MonkeyPatch) -> None:
    prompts: list[str] = []

    async def fake_chat_with_ollama(prompt: str, **_: object) -> str:
        prompts.append(prompt)
        if len(prompts) == 1:
            return (
                "**Personal data**\n• Candidate\n"
                "**Experience**\n• Not specified\n"
                "**Education**\n• MSc Computer Science\n"
                "**Skills**\n• Not specified\n"
                "**Certifications**\n• Not specified\n"
                "**Hobby**\n• Not specified"
            )
        return (
            "**Personal data**\n• Candidate\n"
            "**Experience**\n• Senior Java Engineer at ExampleBank\n"
            "**Education**\n• MSc Computer Science\n"
            "**Skills**\n• Java, Spring Boot, Python, Docker, AWS, Kafka, React, SQL, Kubernetes, GitLab CI/CD, Agile/SAFe\n"
            "**Certifications**\n• Not specified\n"
            "**Hobby**\n• Not specified"
        )

    monkeypatch.setattr(cv_anonymization, "chat_with_ollama", fake_chat_with_ollama)

    result = asyncio.run(cv_anonymization.anonymize_cv_text(
        "Professional Experience: Senior Java Engineer at ExampleBank. Technical Skills: Java, Spring Boot, Python, Docker, AWS, Kafka, React, SQL, Kubernetes, GitLab CI/CD, Agile/SAFe. Education: MSc Computer Science."
    ))

    assert len(prompts) == 2
    assert "previous answer incorrectly omitted professional content" in prompts[1]
    assert "Senior Java Engineer at ExampleBank" in result
    for skill in ("Java", "Spring Boot", "Python", "Docker", "AWS", "Kafka", "React", "SQL", "Kubernetes", "GitLab CI/CD", "Agile/SAFe"):
        assert skill in result
    assert "Experience: Not specified" not in result
    assert "Skills: Not specified" not in result


def test_anonymize_cv_text_removes_introductory_sentence(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_chat_with_ollama(prompt: str, **_: object) -> str:
        return (
            "Here is the anonymized CV content for PDF export:\n"
            "**Personal data**\n• Lugano\n"
            "**Experience**\n• Not specified\n"
            "**Education**\n• Not specified\n"
            "**Skills**\n• Not specified\n"
            "**Certifications**\n• Not specified\n"
            "**Hobby**\n• Not specified"
        )

    monkeypatch.setattr(cv_anonymization, "chat_with_ollama", fake_chat_with_ollama)

    result = asyncio.run(cv_anonymization.anonymize_cv_text("Gabriele Di Somma"))

    assert result == (
        "**Personal data**\n"
        "• Lugano\n"
        "\n"
        "**Experience**\n"
        "• Not specified\n"
        "\n"
        "**Education**\n"
        "• Not specified\n"
        "\n"
        "**Skills**\n"
        "• Not specified\n"
        "\n"
        "**Certifications**\n"
        "• Not specified\n"
        "\n"
        "**Hobby**\n"
        "• Not specified"
    )


def test_normalize_cv_sections_keeps_all_sections_when_present() -> None:
    text = (
        "**Personal data**\n"
        "• Ada\n"
        "**Experience**\n"
        "• Backend Engineer at ExampleCo\n"
        "**Education**\n"
        "• MSc Computer Science\n"
        "**Skills**\n"
        "• Python\n"
        "**Certifications**\n"
        "• AWS Cloud Practitioner\n"
        "**Hobby**\n"
        "• Hiking"
    )

    result = cv_anonymization.normalize_cv_sections(text)

    assert [line for line in result.splitlines() if line.startswith("**")] == EXPECTED_SECTION_HEADINGS
    assert "• Backend Engineer at ExampleCo" in result
    assert "• MSc Computer Science" in result
    assert "• Python" in result
    assert "• AWS Cloud Practitioner" in result
    assert "• Hiking" in result


def test_normalize_cv_sections_restores_missing_sections() -> None:
    result = cv_anonymization.normalize_cv_sections(
        "**Personal data**\n• Ada\n**Experience**\n• Backend Engineer\n**Skills**\n• Python"
    )

    assert [line for line in result.splitlines() if line.startswith("**")] == EXPECTED_SECTION_HEADINGS
    assert result.count("**Education**") == 1
    assert result.count("**Certifications**") == 1
    assert result.count("**Hobby**") == 1
    assert result.count("• Not specified") == 3


def test_normalize_cv_sections_does_not_assign_alternative_headings_after_ollama() -> None:
    result = cv_anonymization.normalize_cv_sections(
        "Contact\n"
        "• Ada\n"
        "Work History\n"
        "• Platform Engineer\n"
        "Technical Skills\n"
        "• Python"
    )

    assert [line for line in result.splitlines() if line.startswith("**")] == EXPECTED_SECTION_HEADINGS
    assert "• Ada" not in result
    assert "• Platform Engineer" not in result
    assert "• Python" not in result
    assert result.count("• Not specified") == 6


def test_normalize_cv_sections_keeps_skills_when_ollama_returns_skill_content() -> None:
    result = cv_anonymization.normalize_cv_sections(
        "**Personal data**\n"
        "• Ada\n"
        "**Skills**\n"
        "• Python, FastAPI, Docker"
    )

    assert "**Skills**\n• Python, FastAPI, Docker" in result


def test_normalize_cv_sections_replaces_empty_sections_with_not_specified() -> None:
    result = cv_anonymization.normalize_cv_sections(
        "**Personal data**\n"
        "**Experience**\n"
        "•   \n"
        "**Skills**\n"
        "• Python"
    )

    assert "**Personal data**\n• Not specified" in result
    assert "**Experience**\n• Not specified" in result
    assert "**Skills**\n• Python" in result


def test_normalize_cv_sections_outputs_all_sections_exactly_once() -> None:
    result = cv_anonymization.normalize_cv_sections(
        "**Skills**\n"
        "• Python\n"
        "**Skills**\n"
        "• FastAPI\n"
        "**Experience**\n"
        "• Developer"
    )

    assert [line for line in result.splitlines() if line.startswith("**")] == EXPECTED_SECTION_HEADINGS
    for heading in EXPECTED_SECTION_HEADINGS:
        assert result.count(heading) == 1
    assert "• Python" in result
    assert "• FastAPI" in result


def test_normalize_cv_sections_does_not_dedupe_repeated_professional_content() -> None:
    result = cv_anonymization.normalize_cv_sections(
        "**Experience**\n"
        "• Built REST APIs\n"
        "• Built REST APIs"
    )

    assert result.count("• Built REST APIs") == 2


def test_cv_anonymization_has_no_regex_or_keyword_section_extraction() -> None:
    source = Path(cv_anonymization.__file__).read_text()

    assert "import re" not in source
    assert "_SECTION_ALIASES" not in source
    for forbidden in ("Core Competencies", "Technical Skills", "Stack", "Technologies", "Tools", "Frameworks", "Methodologies"):
        assert forbidden not in source.replace(cv_anonymization.CV_ANONYMIZATION_PROMPT_TEMPLATE, "")


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

        def extract_text(self) -> str:
            return "M. R. Engineer"

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
        "**Personal data**\n"
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
    assert full_text.count("Personal data") == 1
    assert full_text.count("Experience") == 1
    assert full_text.count("Senior Developer") == 1
    assert full_text.count("Skills") == 1




def test_validate_pdf_has_no_duplicated_pages_rejects_identical_page_text(tmp_path: Path) -> None:
    from reportlab.pdfgen import canvas

    duplicate_pdf = tmp_path / "duplicate-pages.pdf"
    pdf = canvas.Canvas(str(duplicate_pdf), pagesize=(595, 842))
    repeated_text = "Repeated anonymized CV page " * 8
    for _ in range(2):
        pdf.drawString(72, 720, repeated_text)
        pdf.showPage()
    pdf.save()

    with pytest.raises(ToolError, match="duplicated page content"):
        cv_pdf_rendering._validate_pdf_has_no_duplicated_pages(duplicate_pdf)


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
        "**Personal data**\n"
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



def test_render_anonymized_cv_pdf_validates_overlay_before_merging_template(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from reportlab.pdfgen import canvas

    template_path = tmp_path / "template.pdf"
    template = canvas.Canvas(str(template_path), pagesize=(595, 842))
    template.drawString(72, 800, "ReleWant letterhead repeated on every rendered page " * 4)
    template.save()
    output_path = tmp_path / "letterhead-output.pdf"
    validated_paths: list[Path] = []

    def fake_write_text_overlay(text: str, overlay_path: Path, width: float, height: float) -> None:
        pdf = canvas.Canvas(str(overlay_path), pagesize=(width, height))
        pdf.drawString(72, 720, "First generated CV content page with unique experience details.")
        pdf.showPage()
        pdf.drawString(72, 720, "Second generated CV content page with unique education details.")
        pdf.showPage()
        pdf.save()

    original_validate = cv_pdf_rendering._validate_pdf_has_no_duplicated_pages

    def spy_validate(pdf_path: Path) -> None:
        validated_paths.append(pdf_path)
        original_validate(pdf_path)

    monkeypatch.setattr(cv_pdf_rendering, "_write_text_overlay", fake_write_text_overlay)
    monkeypatch.setattr(cv_pdf_rendering, "_validate_pdf_has_no_duplicated_pages", spy_validate)

    cv_pdf_rendering.render_anonymized_cv_pdf(
        "**Experience**\n• Generated content",
        output_path,
        template_path=template_path,
    )

    assert output_path.exists()
    assert validated_paths == [output_path.with_suffix(".overlay.pdf")]

def test_render_anonymized_cv_pdf_rejects_accidentally_duplicated_pages(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    output_path = tmp_path / "duplicated-output.pdf"

    def fake_write_text_overlay(text: str, overlay_path: Path, width: float, height: float) -> None:
        from reportlab.pdfgen import canvas

        pdf = canvas.Canvas(str(overlay_path), pagesize=(width, height))
        repeated_text = "Repeated rendered CV content " * 8
        for _ in range(2):
            pdf.drawString(72, 720, repeated_text)
            pdf.showPage()
        pdf.save()

    monkeypatch.setattr(cv_pdf_rendering, "_write_text_overlay", fake_write_text_overlay)

    with pytest.raises(ToolError, match="duplicated page content"):
        cv_pdf_rendering.render_anonymized_cv_pdf(
            "**Experience**\n• Repeated rendered CV content",
            output_path,
        )
