from __future__ import annotations

import tempfile
from pathlib import Path
from time import perf_counter

from fastmcp.exceptions import ToolError
from pydantic import BaseModel, ConfigDict, Field
from starlette.datastructures import UploadFile

from tools.document import extract_pdf_text, truncate_document_text
from services.document_persistence import answer_document_prompt_from_database
from services.performance import log_performance_event


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
    Successful processing performance is appended to ``performance.log``.
    """
    total_started_at = perf_counter()
    _validate_pdf_upload(upload)
    upload_bytes = 0
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir) / "upload.pdf"
        write_started_at = perf_counter()
        upload_bytes = await _write_upload_to_file(upload, temp_path)
        write_duration_ms = _elapsed_ms(write_started_at)

        extraction_started_at = perf_counter()
        document_text = extract_pdf_text(str(temp_path))
        extraction_duration_ms = _elapsed_ms(extraction_started_at)

    truncate_started_at = perf_counter()
    truncated_text = truncate_document_text(document_text, max_chars=request.max_chars)
    truncate_duration_ms = _elapsed_ms(truncate_started_at)

    workflow_started_at = perf_counter()
    workflow_result = await answer_document_prompt_from_database(
        document_text=truncated_text,
        question=request.question,
    )
    workflow_duration_ms = _elapsed_ms(workflow_started_at)

    log_performance_event(
        "pdf_upload_processed",
        upload_filename=upload.filename,
        upload_bytes=upload_bytes,
        extracted_chars=len(document_text),
        prompt_chars=len(request.question),
        truncated_chars=len(truncated_text),
        max_chars=request.max_chars,
        document_type=workflow_result.document_type,
        collection_name=workflow_result.collection_name,
        record_id=workflow_result.record_id,
        record_existed=workflow_result.record_existed,
        write_duration_ms=write_duration_ms,
        extraction_duration_ms=extraction_duration_ms,
        truncate_duration_ms=truncate_duration_ms,
        database_workflow_duration_ms=workflow_duration_ms,
        total_duration_ms=_elapsed_ms(total_started_at),
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


async def _write_upload_to_file(upload: UploadFile, destination: Path) -> int:
    bytes_written = 0
    with destination.open("wb") as file_obj:
        while chunk := await upload.read(1024 * 1024):
            bytes_written += len(chunk)
            file_obj.write(chunk)

    await upload.close()
    if bytes_written == 0:
        raise ToolError("Uploaded PDF is empty.")
    return bytes_written


def _elapsed_ms(started_at: float) -> float:
    return round((perf_counter() - started_at) * 1000, 3)
