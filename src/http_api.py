from __future__ import annotations

from importlib.util import find_spec
from typing import Any, Iterable

from config import SERVICE_NAME

HTTP_RUNTIME_DEPENDENCIES = ("fastmcp", "multipart", "pydantic", "starlette")
INSTALL_GUIDANCE = (
    "Missing HTTP API dependency: {dependencies}. Install project dependencies with "
    "`python -m pip install -e .`, then start the API with "
    "`python -m uvicorn http_api:app --app-dir src --reload`."
)


class MissingDependencyASGI:
    """Minimal ASGI app that returns actionable setup guidance."""

    def __init__(self, missing_dependencies: Iterable[str]) -> None:
        dependencies = tuple(missing_dependencies)
        self.message = INSTALL_GUIDANCE.format(dependencies=", ".join(dependencies))

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] == "lifespan":
            while True:
                message = await receive()
                if message["type"] == "lifespan.startup":
                    await send({"type": "lifespan.startup.complete"})
                elif message["type"] == "lifespan.shutdown":
                    await send({"type": "lifespan.shutdown.complete"})
                    return

        body = (self.message + "\n").encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 503,
                "headers": [
                    (b"content-type", b"text/plain; charset=utf-8"),
                    (b"content-length", str(len(body)).encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


def get_missing_http_dependencies(
    dependencies: Iterable[str] = HTTP_RUNTIME_DEPENDENCIES,
) -> tuple[str, ...]:
    return tuple(
        dependency for dependency in dependencies if find_spec(dependency) is None
    )


_MISSING_DEPENDENCIES = get_missing_http_dependencies()

if _MISSING_DEPENDENCIES:

    def create_app() -> MissingDependencyASGI:
        return MissingDependencyASGI(_MISSING_DEPENDENCIES)

else:
    from starlette.applications import Starlette
    from starlette.responses import HTMLResponse, JSONResponse, Response
    from starlette.routing import Route

    from routers.cv_export import router as cv_export_router
    from routers.document import router as document_router
    from routers.prompt import router as prompt_router
    from services.document_upload import PdfUploadResponse
    from services.prompt_router import PromptExecutionRequest, PromptExecutionResponse

    def build_openapi_schema() -> dict[str, Any]:
        return {
            "openapi": "3.1.0",
            "info": {
                "title": SERVICE_NAME,
                "version": "0.1.0",
                "description": "HTTP API for frontend prompt routing and database-first PDF answers.",
            },
            "paths": {
                "/api/cv/anonymized-pdf": {
                    "post": {
                        "tags": ["cv"],
                        "summary": "Upload a CV PDF and receive an anonymized version rendered on ReleWant letterhead.",
                        "description": "Extracts CV PDF text, asks Ollama to anonymize personally identifiable information, renders the anonymized content onto stationery/relewant-sa-letterhead.pdf, streams the generated PDF, and deletes temporary files after delivery.",
                        "requestBody": {
                            "required": True,
                            "content": {
                                "multipart/form-data": {
                                    "schema": {
                                        "type": "object",
                                        "required": ["file"],
                                        "properties": {
                                            "file": {
                                                "type": "string",
                                                "format": "binary",
                                                "description": "CV PDF to anonymize and render.",
                                            }
                                        }
                                    }
                                }
                            }
                        },
                        "responses": {
                            "200": {
                                "description": "Generated anonymized CV PDF.",
                                "content": {
                                    "application/pdf": {
                                        "schema": {"type": "string", "format": "binary"}
                                    }
                                },
                            },
                            "400": {
                                "description": "Invalid upload, extraction failure, Ollama failure, missing template, or PDF rendering failure."
                            },
                            "500": {
                                "description": "Temporary file creation or file delivery failure."
                            },
                        },
                    }
                },
                "/api/documents/pdf": {
                    "post": {
                        "tags": ["documents"],
                        "summary": "Upload a PDF and answer through the database-first CV/insurance workflow.",
                        "description": "The API extracts PDF text server-side, detects CV versus insurance, checks the candidates or insurances database collection, extracts only when no record exists, retrieves the saved record, and answers from that database record. The database is the single source of truth for answers.",
                        "requestBody": {
                            "required": True,
                            "content": {
                                "multipart/form-data": {
                                    "schema": {
                                        "type": "object",
                                        "required": ["file", "question"],
                                        "properties": {
                                            "file": {
                                                "type": "string",
                                                "format": "binary",
                                                "description": "PDF file to process.",
                                            },
                                            "question": {
                                                "type": "string",
                                                "minLength": 1,
                                                "description": "Question to answer using the database record for the uploaded PDF.",
                                            },
                                            "max_chars": {
                                                "type": "integer",
                                                "default": 30000,
                                                "minimum": 1,
                                                "description": "Maximum extracted PDF characters available for classification and new-record extraction.",
                                            },
                                        },
                                    }
                                }
                            },
                        },
                        "responses": {
                            "200": {
                                "description": "Ollama answer based on the uploaded PDF.",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "$ref": "#/components/schemas/PdfUploadResponse"
                                        }
                                    }
                                },
                            },
                            "400": {
                                "description": "Invalid upload, PDF extraction failure, or Ollama error."
                            },
                            "422": {"description": "Invalid form fields."},
                        },
                    }
                },
                "/api/prompts/execute": {
                    "post": {
                        "tags": ["prompts"],
                        "summary": "Route a frontend message, enrich Ollama with the inferred tool, and return only the answer.",
                        "requestBody": {
                            "required": True,
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/PromptExecutionRequest"
                                    }
                                }
                            },
                        },
                        "responses": {
                            "200": {
                                "description": "Ollama prompt response.",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "$ref": "#/components/schemas/PromptExecutionResponse"
                                        }
                                    }
                                },
                            },
                            "400": {"description": "Invalid prompt or tool arguments."},
                            "422": {"description": "Invalid request body."},
                        },
                    }
                },
            },
            "components": {
                "schemas": {
                    "PdfUploadResponse": PdfUploadResponse.model_json_schema(
                        ref_template="#/components/schemas/{model}"
                    ),
                    "PromptExecutionRequest": PromptExecutionRequest.model_json_schema(
                        ref_template="#/components/schemas/{model}"
                    ),
                    "PromptExecutionResponse": PromptExecutionResponse.model_json_schema(
                        ref_template="#/components/schemas/{model}"
                    ),
                }
            },
        }

    async def openapi_schema(_: object) -> Response:
        return JSONResponse(build_openapi_schema())

    async def swagger_docs(_: object) -> Response:
        return HTMLResponse("""
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>Smart IDE Services API Docs</title>
    <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css" />
  </head>
  <body>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script>
      window.ui = SwaggerUIBundle({
        url: '/openapi.json',
        dom_id: '#swagger-ui',
        deepLinking: true,
        presets: [SwaggerUIBundle.presets.apis],
      });
    </script>
  </body>
</html>
""".strip())

    async def api_hint(_: object) -> Response:
        return JSONResponse(
            {
                "service": SERVICE_NAME,
                "routes": [
                    "POST /api/documents/pdf",
                    "POST /api/cv/anonymized-pdf",
                    "POST /api/prompts/execute",
                ],
                "docs": "Open Swagger UI at /docs or fetch the OpenAPI schema at /openapi.json.",
            }
        )

    def create_app() -> Starlette:
        return Starlette(
            debug=False,
            routes=[
                Route("/", api_hint, methods=["GET"]),
                Route("/docs", swagger_docs, methods=["GET"]),
                Route("/openapi.json", openapi_schema, methods=["GET"]),
                *document_router.routes,
                *cv_export_router.routes,
                *prompt_router.routes,
            ],
        )


app = create_app()
