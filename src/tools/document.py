from __future__ import annotations

from pathlib import Path
import subprocess

from fastmcp.exceptions import ToolError


def extract_pdf_text(file_path: str) -> str:
    path = Path(file_path).expanduser().resolve()

    if not path.exists():
        raise ToolError(f"File not found: {path}")
    if path.suffix.lower() != ".pdf":
        raise ToolError(f"Expected a PDF file, got: {path.name}")

    try:
        result = subprocess.run(
            ["pdftotext", str(path), "-"],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise ToolError("pdftotext is required but was not found in PATH") from exc
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        raise ToolError(
            f"Failed to extract text from PDF '{path.name}': {stderr or exc}"
        ) from exc

    text = result.stdout.strip()
    if not text:
        raise ToolError(f"No extractable text found in PDF: {path.name}")

    return text


def truncate_document_text(document_text: str, max_chars: int) -> str:
    if max_chars <= 0:
        raise ToolError("max_chars must be greater than 0")

    cleaned = document_text.strip()
    if len(cleaned) <= max_chars:
        return cleaned

    truncated_notice = "\n\n[Document truncated due to length before model call.]"
    allowed_length = max_chars - len(truncated_notice)
    if allowed_length <= 0:
        raise ToolError("max_chars is too small to include truncation metadata")

    return f"{cleaned[:allowed_length].rstrip()}{truncated_notice}"
