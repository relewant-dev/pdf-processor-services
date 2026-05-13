from __future__ import annotations

from fastmcp.exceptions import ToolError
from pydantic import ValidationError
from starlette.datastructures import UploadFile
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route, Router
from starlette.status import HTTP_400_BAD_REQUEST

from services.document_upload import PdfUploadRequest, process_pdf_upload


async def post_pdf_upload(request: Request) -> Response:
    try:
        form = await request.form()
        upload = form.get("file")
        if not isinstance(upload, UploadFile):
            raise ToolError(
                "multipart field 'file' is required and must contain a PDF upload."
            )

        upload_request = PdfUploadRequest.model_validate(
            {
                "question": form.get("question"),
                "max_chars": form.get("max_chars", 30000),
            }
        )
        response = await process_pdf_upload(upload, upload_request)
    except ValidationError as exc:
        return JSONResponse(
            {"detail": exc.errors()},
            status_code=422,
        )
    except ToolError as exc:
        return JSONResponse({"detail": str(exc)}, status_code=HTTP_400_BAD_REQUEST)

    return JSONResponse(response.model_dump())


router = Router(routes=[Route("/api/documents/pdf", post_pdf_upload, methods=["POST"])])
