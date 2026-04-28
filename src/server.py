from __future__ import annotations

import os
from typing import Any

import httpx
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

SERVICE_NAME = "smart-ide-services"
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5vl:7b")

mcp = FastMCP(name=SERVICE_NAME, mask_error_details=True)


async def _chat_with_ollama(prompt: str) -> str:
    """Send a prompt to the local Ollama instance and return generated text."""
    if not prompt.strip():
        raise ToolError("Prompt must not be empty.")

    payload: dict[str, Any] = {
        "model": OLLAMA_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(f"{OLLAMA_URL}/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        raise ToolError(
            f"Failed to reach Ollama at {OLLAMA_URL}. Ensure 'ollama serve' is running."
        ) from exc

    message = data.get("message", {})
    content = message.get("content")
    if not content:
        raise ToolError("Ollama returned an unexpected response shape.")
    return content


@mcp.tool(description="Send a user prompt to local Ollama and return the model output.")
async def send_prompt(prompt: str) -> str:
    """Receives a user prompt and returns model output from local Ollama."""
    return await _chat_with_ollama(prompt)


@mcp.tool(description="Check Ollama reachability and verify the configured model exists.")
async def health_check() -> dict[str, Any]:
    """Checks if Ollama is reachable and the configured model exists locally."""
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


@mcp.prompt
def chat_prompt(user_message: str) -> str:
    """Create a reusable prompt template for user chat messages."""
    return f"User message: {user_message}"


def main() -> None:
    """Run as an MCP service (stdio transport by default)."""
    mcp.run()


if __name__ == "__main__":
    main()
