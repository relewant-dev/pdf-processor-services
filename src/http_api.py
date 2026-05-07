from __future__ import annotations

from typing import Any

from starlette.applications import Starlette
from starlette.responses import HTMLResponse, JSONResponse, Response
from starlette.routing import Route

from config import SERVICE_NAME
from routers.prompt import router as prompt_router
from services.prompt_router import (
    PromptExecutionRequest,
    PromptExecutionResponse,
    PromptRoute,
)


def build_openapi_schema() -> dict[str, Any]:
    return {
        "openapi": "3.1.0",
        "info": {
            "title": SERVICE_NAME,
            "version": "0.1.0",
            "description": "HTTP API for frontend prompt routing and execution.",
        },
        "paths": {
            "/api/prompts/route": {
                "get": {
                    "tags": ["prompts"],
                    "summary": "Route a frontend prompt to the recommended tool.",
                    "parameters": [
                        {
                            "name": "prompt",
                            "in": "query",
                            "required": True,
                            "description": "Prompt message from the frontend.",
                            "schema": {"type": "string", "minLength": 1},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Recommended prompt route.",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/PromptRoute"}
                                }
                            },
                        },
                        "400": {"description": "Invalid prompt."},
                    },
                }
            },
            "/api/prompts/execute": {
                "post": {
                    "tags": ["prompts"],
                    "summary": "Execute a frontend prompt using the inferred or requested tool.",
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
                            "description": "Prompt execution result.",
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
                "PromptRoute": PromptRoute.model_json_schema(ref_template="#/components/schemas/{model}"),
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
    return HTMLResponse(
        """
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
""".strip()
    )


async def api_hint(_: object) -> Response:
    return JSONResponse(
        {
            "service": SERVICE_NAME,
            "routes": [
                "GET /api/prompts/route?prompt=...",
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
            *prompt_router.routes,
        ],
    )


app = create_app()
