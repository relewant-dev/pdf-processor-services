from __future__ import annotations

import tempfile
from pathlib import Path

from fastmcp.exceptions import ToolError
from pydantic import BaseModel, ConfigDict, Field
from starlette.datastructures import UploadFile

from tools.document import extract_pdf_text, truncate_document_text
from services.document_persistence import answer_document_prompt_from_database


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
    """Extract PDF text, then answer through the database-first workflow.

    The uploaded PDF is classified and checked against the appropriate database
    collection before any structured extraction runs. Answers are generated from
    the retrieved database record rather than directly from the PDF text.
    """
    _validate_pdf_upload(upload)
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir) / "upload.pdf"
        await _write_upload_to_file(upload, temp_path)
        document_text = extract_pdf_text(str(temp_path))

    truncated_text = truncate_document_text(document_text, max_chars=request.max_chars)
    workflow_result = await answer_document_prompt_from_database(
        document_text=truncated_text,
        question=request.question,
    )
    return PdfUploadResponse(response=workflow_result.response)


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
