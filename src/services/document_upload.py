from __future__ import annotations

import tempfile
from pathlib import Path

from fastmcp.exceptions import ToolError
from pydantic import BaseModel, ConfigDict, Field
from starlette.datastructures import UploadFile

from clients.ollama import chat_with_ollama
from tools.document import (
    build_document_prompt,
    extract_pdf_text,
    truncate_document_text,
)


class PdfUploadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(
        ...,
        min_length=1,
        description="Question to answer using the uploaded PDF content.",
    )
    max_chars: int = Field(
        30000,
        gt=0,
        description="Maximum extracted PDF characters to include in the Ollama prompt.",
    )


class PdfUploadResponse(BaseModel):
    response: str


async def process_pdf_upload(
    upload: UploadFile,
    request: PdfUploadRequest,
) -> PdfUploadResponse:
    """Extract PDF text server-side, then ask Ollama about that text.

    Ollama does not receive or parse the raw PDF binary. Image-only or scanned PDFs
    without an extractable text layer require OCR before this endpoint can answer.
    """
    _validate_pdf_upload(upload)
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir) / "upload.pdf"
        await _write_upload_to_file(upload, temp_path)
        document_text = extract_pdf_text(str(temp_path))

    truncated_text = truncate_document_text(document_text, max_chars=request.max_chars)
    prompt = build_document_prompt(truncated_text, request.question)
    model_result = await chat_with_ollama(prompt)
    return PdfUploadResponse(response=model_result)


def _validate_pdf_upload(upload: UploadFile) -> None:
    filename = upload.filename or ""
    content_type = upload.content_type or ""
    if not filename.lower().endswith(".pdf"):
        raise ToolError("Uploaded file must use a .pdf filename.")
    if content_type and content_type not in ("application/pdf", "application/x-pdf"):
        raise ToolError(
            f"Uploaded file must be a PDF, got content type: {content_type}"
        )


async def _write_upload_to_file(upload: UploadFile, destination: Path) -> None:
    bytes_written = 0
    with destination.open("wb") as file_obj:
        while chunk := await upload.read(1024 * 1024):
            bytes_written += len(chunk)
            file_obj.write(chunk)

    await upload.close()
    if bytes_written == 0:
        raise ToolError("Uploaded PDF is empty.")
