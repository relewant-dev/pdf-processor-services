from __future__ import annotations

from typing import Any

import httpx
from fastmcp.exceptions import ToolError

from config import (
    OLLAMA_EMBEDDING_MODEL,
    OLLAMA_MODEL,
    OLLAMA_TIMEOUT_SECONDS,
    OLLAMA_URL,
)
from logging_config import get_logger

logger = get_logger()


async def chat_with_ollama(prompt: str) -> str:
    logger.debug("Calling Ollama chat with prompt_length=%s", len(prompt))
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
        logger.error("Ollama chat timed out.")
        raise ToolError(
            f"Ollama timed out after {OLLAMA_TIMEOUT_SECONDS:.0f}s. "
            "Try a smaller document, a faster model, or increase OLLAMA_TIMEOUT_SECONDS."
        ) from exc
    except httpx.HTTPError as exc:
        logger.error("Ollama chat request failed at url=%s", OLLAMA_URL)
        raise ToolError(
            f"Failed to reach Ollama at {OLLAMA_URL}. Ensure 'ollama serve' is running."
        ) from exc

    message = data.get("message", {})
    content = message.get("content")
    if not content:
        raise ToolError("Ollama returned an unexpected response shape.")
    return content


async def ollama_health() -> dict[str, Any]:
    logger.debug("Checking Ollama health at url=%s", OLLAMA_URL)
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            tags_resp = await client.get(f"{OLLAMA_URL}/api/tags")
            tags_resp.raise_for_status()
            models = tags_resp.json().get("models", [])
    except httpx.HTTPError as exc:
        logger.error("Ollama health check failed at url=%s", OLLAMA_URL)
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


async def embed_with_ollama(text: str) -> list[float]:
    logger.debug("Calling Ollama embeddings with text_length=%s", len(text))
    if not text.strip():
        raise ToolError("Text to embed must not be empty.")

    payload: dict[str, Any] = {
        "model": OLLAMA_EMBEDDING_MODEL,
        "input": text,
    }

    try:
        async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT_SECONDS) as client:
            response = await client.post(f"{OLLAMA_URL}/api/embed", json=payload)
            response.raise_for_status()
            data = response.json()
    except httpx.ReadTimeout as exc:
        logger.error("Ollama embedding request timed out.")
        raise ToolError(
            f"Ollama embedding timed out after {OLLAMA_TIMEOUT_SECONDS:.0f}s. "
            "Try a smaller document or increase OLLAMA_TIMEOUT_SECONDS."
        ) from exc
    except httpx.HTTPError as exc:
        logger.error("Ollama embedding request failed at url=%s", OLLAMA_URL)
        raise ToolError(
            f"Failed to reach Ollama embeddings at {OLLAMA_URL}. "
            "Ensure 'ollama serve' is running."
        ) from exc

    embeddings = data.get("embeddings")
    if not isinstance(embeddings, list) or not embeddings:
        raise ToolError("Ollama returned an unexpected embedding response shape.")
    embedding = embeddings[0]
    if not isinstance(embedding, list) or not embedding:
        raise ToolError("Ollama returned an unexpected embedding vector shape.")
    return [float(value) for value in embedding]
