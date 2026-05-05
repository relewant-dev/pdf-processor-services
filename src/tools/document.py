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
        raise ToolError(f"Failed to extract text from PDF '{path.name}': {stderr or exc}") from exc

    text = result.stdout.strip()
    if not text:
        raise ToolError(f"No extractable text found in PDF: {path.name}")

    return text


def build_document_prompt(document_text: str, question: str) -> str:
    return (
        "You are processing a PDF document. Use only the content below to answer the user question.\n\n"
        f"User question:\n{question}\n\n"
        "Document content:\n"
        f"{document_text}"
    )
