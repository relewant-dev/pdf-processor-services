from __future__ import annotations

from json import JSONDecodeError

from fastmcp.exceptions import ToolError
from pydantic import ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route, Router
from starlette.status import HTTP_400_BAD_REQUEST

from services.prompt_router import (
    PromptExecutionRequest,
    execute_prompt_tool,
    route_prompt,
)


async def get_prompt_route(request: Request) -> Response:
    prompt = request.query_params.get("prompt", "")
    try:
        route = route_prompt(prompt)
    except ToolError as exc:
        return JSONResponse({"detail": str(exc)}, status_code=HTTP_400_BAD_REQUEST)

    return JSONResponse(route.model_dump())


async def post_prompt_execute(request: Request) -> Response:
    try:
        payload = await request.json()
        execution_request = PromptExecutionRequest.model_validate(payload)
        response = await execute_prompt_tool(execution_request)
    except JSONDecodeError as exc:
        return JSONResponse({"detail": str(exc)}, status_code=HTTP_400_BAD_REQUEST)
    except ValidationError as exc:
        return JSONResponse(
            {"detail": exc.errors()},
            status_code=422,
        )
    except ToolError as exc:
        return JSONResponse({"detail": str(exc)}, status_code=HTTP_400_BAD_REQUEST)

    return JSONResponse(response.model_dump())


router = Router(
    routes=[
        Route("/api/prompts/route", get_prompt_route, methods=["GET"]),
        Route("/api/prompts/execute", post_prompt_execute, methods=["POST"]),
    ]
)
