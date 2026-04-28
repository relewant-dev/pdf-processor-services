# smart-ide-services

Backend MCP service for Smart IDE App.

## What this provides

A runnable FastMCP server (following the official FastMCP quickstart pattern) with:

- `send_prompt(prompt)` tool to receive user messages and route them to local Ollama.
- `health_check()` tool to verify local Ollama availability and model readiness.
- `chat_prompt(user_message)` MCP prompt template.
- Default model set to `qwen2.5vl:7b`.

## Prerequisites

- Python 3.10+
- Ollama installed and running locally
- Model pulled locally:

```bash
ollama pull qwen2.5vl:7b
```

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Run the service

Start Ollama in another terminal:

```bash
ollama serve
```

Run server directly (stdio transport):

```bash
smart-ide-service
```

Or run through FastMCP CLI (official docs style):

```bash
fastmcp run src/smart_ide_services/server.py:mcp
```

Run over HTTP transport when needed:

```bash
fastmcp run src/smart_ide_services/server.py:mcp --transport http --port 8000
```

## Call it from a FastMCP client

When running with HTTP transport on port 8000:

```python
import asyncio
from fastmcp import Client

client = Client("http://localhost:8000/mcp")

async def main() -> None:
    async with client:
        result = await client.call_tool("send_prompt", {"prompt": "Hello from Smart IDE"})
        print(result.data)

asyncio.run(main())
```

## MCP components

### Tool: `send_prompt`

Input:

- `prompt` (string): user message.

Output:

- string response from local Ollama `qwen2.5vl:7b`.

### Tool: `health_check`

Output JSON includes:

- configured Ollama URL
- configured model
- model availability flag
- suggested `ollama pull` command when model is missing

### Prompt: `chat_prompt`

Input:

- `user_message` (string)

Output:

- reusable prompt text message

## Environment variables

- `OLLAMA_URL`: Ollama base URL (default `http://127.0.0.1:11434`).
- `OLLAMA_MODEL`: model name (default `qwen2.5vl:7b`).
