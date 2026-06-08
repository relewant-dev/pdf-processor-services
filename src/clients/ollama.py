from __future__ import annotations

from typing import Any

import httpx
from fastmcp.exceptions import ToolError

from config import OLLAMA_MODEL, OLLAMA_TIMEOUT_SECONDS, OLLAMA_URL


async def chat_with_ollama(prompt: str, response_format: Any | None = None) -> str:
    if not prompt.strip():
        raise ToolError("Prompt must not be empty.")

    payload: dict[str, Any] = {
        "model": OLLAMA_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }
    if response_format is not None:
        payload["format"] = response_format

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
    except httpx.HTTPError as exc:
        raise ToolError(
            f"Failed to reach Ollama at {OLLAMA_URL}. Ensure 'ollama serve' is running."
        ) from exc

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
    except httpx.HTTPError as exc:
        raise ToolError(
            f"Ollama is not reachable at {OLLAMA_URL}. Start it with: ollama serve"
        ) from exc

    has_model = any(model.get("name") == OLLAMA_MODEL for model in models)
    return {
        "ollama_url": OLLAMA_URL,
        "model": OLLAMA_MODEL,
        "model_available": has_model,
        "next_step": None if has_model else f"ollama pull {OLLAMA_MODEL}",
    }
