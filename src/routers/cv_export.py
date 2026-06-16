from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from time import perf_counter

from fastmcp.exceptions import ToolError
from pydantic import ValidationError
from starlette.background import BackgroundTask
from starlette.datastructures import UploadFile
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response
from starlette.routing import Route, Router
from starlette.status import HTTP_400_BAD_REQUEST, HTTP_500_INTERNAL_SERVER_ERROR

from logging_config import get_logger
from services.cv_anonymization import anonymize_cv_text
from services.cv_extraction import extract_cv_text_from_upload
from services.cv_pdf_rendering import render_anonymized_cv_pdf

logger = get_logger()


async def post_anonymized_cv_export(request: Request) -> Response:
    temp_dir: Path | None = None
    try:
        form = await request.form()
        upload = form.get("file")
        if not isinstance(upload, UploadFile):
            raise ToolError("multipart field 'file' is required and must contain a CV PDF upload.")

        logger.info("cv_export_upload_received filename=%s content_type=%s", upload.filename, upload.content_type)
        extracted_text = await extract_cv_text_from_upload(upload)
        logger.info("cv_export_text_extraction_completed filename=%s extracted_chars=%s", upload.filename, len(extracted_text))

        logger.info("cv_export_ollama_anonymization_started filename=%s", upload.filename)
        anonymized_text = await anonymize_cv_text(extracted_text)
        logger.info("cv_export_ollama_anonymization_completed filename=%s anonymized_chars=%s", upload.filename, len(anonymized_text))

        temp_dir = Path(tempfile.mkdtemp(prefix="anonymized-cv-"))
        output_path = temp_dir / "anonymized-cv.pdf"
        logger.info("cv_export_pdf_generation_started output_path=%s", output_path)
        render_anonymized_cv_pdf(anonymized_text, output_path)
        logger.info("cv_export_pdf_generation_completed output_path=%s", output_path)

        return FileResponse(
            output_path,
            media_type="application/pdf",
            filename="anonymized-cv.pdf",
            background=BackgroundTask(_delete_temp_dir, temp_dir),
        )
    except ValidationError as exc:
        logger.exception("cv_export_validation_failed")
        if temp_dir is not None:
            _delete_temp_dir(temp_dir)
        return JSONResponse({"detail": exc.errors()}, status_code=422)
    except ToolError as exc:
        logger.exception("cv_export_failed error=%s", exc)
        if temp_dir is not None:
            _delete_temp_dir(temp_dir)
        return JSONResponse({"detail": str(exc)}, status_code=HTTP_400_BAD_REQUEST)
    except OSError as exc:
        logger.exception("cv_export_file_delivery_or_tempfile_failed error=%s", exc)
        if temp_dir is not None:
            _delete_temp_dir(temp_dir)
        return JSONResponse(
            {"detail": f"Failed to create or deliver generated CV PDF: {exc}"},
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        )


def _delete_temp_dir(temp_dir: Path) -> None:
    shutil.rmtree(temp_dir, ignore_errors=True)
    logger.info("cv_export_temporary_file_deleted temp_dir=%s", temp_dir)


router = Router(routes=[Route("/api/cv/anonymized-pdf", post_anonymized_cv_export, methods=["POST"])])
