from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from fastmcp.exceptions import ToolError
from starlette.datastructures import UploadFile

from tools.document import extract_pdf_text

logger = logging.getLogger(__name__)

PDF_CONTENT_TYPES = {"application/pdf", "application/x-pdf"}


def validate_cv_pdf_upload(upload: UploadFile) -> None:
    filename = upload.filename or ""
    content_type = upload.content_type or ""
    if not filename:
        raise ToolError("multipart field 'file' is required and must contain a PDF upload.")
    if not filename.lower().endswith(".pdf"):
        raise ToolError("Uploaded CV must use a .pdf filename.")
    if content_type and content_type not in PDF_CONTENT_TYPES:
        raise ToolError(f"Uploaded CV must be a PDF, got content type: {content_type}")


async def extract_cv_text_from_upload(upload: UploadFile) -> str:
    """Persist an uploaded CV PDF temporarily and extract its text."""
    validate_cv_pdf_upload(upload)
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir) / "cv-upload.pdf"
        bytes_written = await _write_upload_to_file(upload, temp_path)
        if bytes_written == 0:
            raise ToolError("Uploaded CV PDF is empty.")
        text = extract_pdf_text(str(temp_path))
        page_count = _count_pdf_pages(temp_path)
        logger.info(
            "cv_extraction_completed filename=%s extracted_text_chars=%s page_count=%s",
            upload.filename,
            len(text),
            page_count,
        )
        return text


async def _write_upload_to_file(upload: UploadFile, destination: Path) -> int:
    try:
        bytes_written = 0
        with destination.open("wb") as file_obj:
            while chunk := await upload.read(1024 * 1024):
                bytes_written += len(chunk)
                file_obj.write(chunk)
        return bytes_written
    except OSError as exc:
        raise ToolError(f"Failed to create temporary CV upload file: {exc}") from exc
    finally:
        await upload.close()


def _count_pdf_pages(pdf_path: Path) -> int | None:
    try:
        from pypdf import PdfReader

        return len(PdfReader(str(pdf_path)).pages)
    except Exception as exc:
        logger.warning("cv_extraction_page_count_failed path=%s error=%s", pdf_path, exc)
        return None
