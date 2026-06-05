from pathlib import Path

import pytest
from fastmcp.exceptions import ToolError

from tools.document import extract_pdf_text, truncate_document_text


def test_extract_pdf_text_raises_for_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.pdf"

    with pytest.raises(ToolError, match="File not found"):
        extract_pdf_text(str(missing))


def test_extract_pdf_text_raises_for_non_pdf(tmp_path: Path) -> None:
    txt_file = tmp_path / "notes.txt"
    txt_file.write_text("hello", encoding="utf-8")

    with pytest.raises(ToolError, match="Expected a PDF file"):
        extract_pdf_text(str(txt_file))


def test_truncate_document_text_no_truncation_when_short() -> None:
    text = "short text"

    assert truncate_document_text(text, max_chars=100) == text


def test_truncate_document_text_truncates_with_notice() -> None:
    text = "x" * 200

    truncated = truncate_document_text(text, max_chars=80)

    assert len(truncated) <= 80
    assert "Document truncated due to length" in truncated
