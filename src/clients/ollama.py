from __future__ import annotations

from typing import Any

import httpx
from fastmcp.exceptions import ToolError

from config import OLLAMA_MODEL, OLLAMA_TIMEOUT_SECONDS, OLLAMA_URL


def _short_response_body(response: httpx.Response, max_chars: int = 500) -> str:
    body = response.text.strip()
    if len(body) > max_chars:
        return f"{body[:max_chars]}..."
    return body


def _ollama_status_error_message(response: httpx.Response) -> str:
    body = _short_response_body(response)
    detail = f" Ollama response: {body}" if body else ""
    return (
        f"Ollama at {OLLAMA_URL} returned HTTP {response.status_code} for model "
        f"'{OLLAMA_MODEL}'.{detail} Ensure the model is available with "
        f"'ollama pull {OLLAMA_MODEL}', or set OLLAMA_MODEL to an installed model."
    )


def _ollama_connection_error_message() -> str:
    return (
        f"Failed to reach Ollama at {OLLAMA_URL}. Ensure 'ollama serve' is running "
        "where this service can reach it. If this API is running in Docker or WSL, "
        "127.0.0.1 points at that environment, not your host; set OLLAMA_URL to the "
        "reachable host address, for example http://host.docker.internal:11434."
    )


async def chat_with_ollama(prompt: str) -> str:
    if not prompt.strip():
        raise ToolError("Prompt must not be empty.")

    payload: dict[str, Any] = {
        "model": OLLAMA_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }

    try:
        async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT_SECONDS) as client:
            response = await client.post(f"{OLLAMA_URL}/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
    except httpx.ReadTimeout as exc:
        raise ToolError(
            f"Ollama timed out after {OLLAMA_TIMEOUT_SECONDS:.0f}s. "
            "Try a smaller document, a faster model, or increase OLLAMA_TIMEOUT_SECONDS."
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise ToolError(_ollama_status_error_message(exc.response)) from exc
    except httpx.HTTPError as exc:
        raise ToolError(_ollama_connection_error_message()) from exc

    message = data.get("message", {})
    content = message.get("content")
    if not content:
        raise ToolError("Ollama returned an unexpected response shape.")
    return content


async def ollama_health() -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            tags_resp = await client.get(f"{OLLAMA_URL}/api/tags")
            tags_resp.raise_for_status()
            models = tags_resp.json().get("models", [])
    except httpx.HTTPStatusError as exc:
        raise ToolError(_ollama_status_error_message(exc.response)) from exc
    except httpx.HTTPError as exc:
        raise ToolError(_ollama_connection_error_message()) from exc

    has_model = any(model.get("name") == OLLAMA_MODEL for model in models)
    return {
        "ollama_url": OLLAMA_URL,
        "model": OLLAMA_MODEL,
        "model_available": has_model,
        "next_step": None if has_model else f"ollama pull {OLLAMA_MODEL}",
    }
