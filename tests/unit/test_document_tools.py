from pathlib import Path

import pytest
from fastmcp.exceptions import ToolError

from tools.document import build_document_prompt, extract_pdf_text


def test_build_document_prompt_contains_question_and_document() -> None:
    prompt = build_document_prompt("Document text", "What is this?")

    assert "What is this?" in prompt
    assert "Document text" in prompt


def test_extract_pdf_text_raises_for_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.pdf"

    with pytest.raises(ToolError, match="File not found"):
        extract_pdf_text(str(missing))


def test_extract_pdf_text_raises_for_non_pdf(tmp_path: Path) -> None:
    txt_file = tmp_path / "notes.txt"
    txt_file.write_text("hello", encoding="utf-8")

    with pytest.raises(ToolError, match="Expected a PDF file"):
        extract_pdf_text(str(txt_file))
