# Smart IDE App

[![Build Status](https://img.shields.io/github/actions/workflow/status/relewant-dev/smart-ide-services/ci.yaml?style=for-the-badge&logo=github-actions&logoColor=white&color=2ecc71)](https://github.com/relewant-dev/smart-ide-services/actions)
[![Latest Version](https://img.shields.io/github/v/release/relewant-dev/smart-ide-services?style=for-the-badge&logo=semver&logoColor=white&color=3498db)](https://github.com/relewant-dev/smart-ide-services/releases)
[![License](https://img.shields.io/github/license/relewant-dev/smart-ide-services?style=for-the-badge&logo=opensourceinitiative&logoColor=white&color=f39c12)](./LICENSE)
[![Conventional Commits](https://img.shields.io/badge/Conventional%20Commits-1.0.0-yellow.svg?style=for-the-badge&logo=git&logoColor=white&color=e74c3c)](https://conventionalcommits.org)

Backend for Smart IDE App.

This project uses a GitHub Actions release pipeline (`.github/workflows/ci.yaml`) with Conventional Commit linting and semantic-release to automate tagging and release notes on pushes to `main`.

## Git commit hook (Conventional Commits)

This repository includes a `commit-msg` hook that validates commit messages against the Conventional Commits format.

### Enable the hook

Run this once after cloning:

```bash
git config core.hooksPath .githooks
```

### Accepted format

```text
<type>[optional scope][!]: <description>
```

Examples:

- `feat(auth): add OAuth callback handler`
- `fix: handle null API response`
- `refactor!: remove legacy settings endpoint`

Allowed types:

- `feat`
- `fix`
- `docs`
- `style`
- `refactor`
- `perf`
- `test`
- `build`
- `ci`
- `chore`
- `revert`

## Project structure (recommended)

To evolve this service into a smart IDE backend, prefer the following architecture:

- `src/server.py`: MCP bootstrap and service wiring only.
- `src/config.py`: environment parsing and runtime settings.
- `src/logging_config.py`: rotating log setup.
- `src/clients/ollama.py`: Ollama HTTP client adapter.
- `src/tools/backend.py`: backend planning/routing tool logic.
- `src/domain/blueprints.py`: stack blueprint registry and resolution.
- `src/clients/`: adapters for LLM providers (starting with Ollama).
- `src/tools/`: MCP tool definitions grouped by capability.
- `src/prompts/`: reusable prompt templates and prompt builders.
- `src/domain/`: core business logic and shared schemas.
- `tests/unit` and `tests/integration`: test separation by speed and dependency.

This keeps transport concerns, provider clients, and tool logic decoupled so the platform can scale to more IDE features safely.

## Testing skill routing

You can validate stack skill routing and blueprint exposure locally with:

```bash
python -m compileall src tests
pytest -q
```

Coverage includes:
- intent routing for Java/Spring, Node/Express/TypeScript, and Python/FastAPI;
- invalid stack intent handling;
- blueprint list contains expected generation skills.

## Rotative logs for MCP tools

The MCP server now writes tool invocation logs using a rotating file handler.

Environment variables:
- `LOG_LEVEL` (default: `INFO`)
- `LOG_FILE` (default: `smart-ide-services.log`)
- `LOG_MAX_BYTES` (default: `1048576`)
- `LOG_BACKUP_COUNT` (default: `5`)

Example:

```bash
LOG_FILE=logs/mcp.log LOG_MAX_BYTES=2097152 LOG_BACKUP_COUNT=10 python src/server.py
```

## PDF processing and Ollama timeout tuning

The `process_pdf` MCP tool sends extracted PDF text to Ollama. Large PDFs may take longer to complete.

Environment variables:
- `OLLAMA_TIMEOUT_SECONDS` (default: `300`)

Example:

```bash
OLLAMA_TIMEOUT_SECONDS=600 python src/server.py
```

If you still get timeouts, try reducing prompt size by passing `max_chars` in `process_pdf`.

## Frontend prompt router API

The HTTP API exposes prompt routing endpoints that a frontend can call before or during prompt execution.

### Run the HTTP API locally

Install the project dependencies, then start Uvicorn from the repository root using the same Python environment:

```bash
python -m pip install -e .
python -m uvicorn http_api:app --app-dir src --reload
```

Using `python -m uvicorn` helps avoid accidentally running a globally installed Uvicorn that cannot see this project's installed dependencies. If startup reports `Missing HTTP API dependency: starlette`, reinstall the project dependencies in the Python environment that launches Uvicorn:

```bash
python -m pip install -e .
```

A route summary is available at `http://127.0.0.1:8000/`. Swagger UI is available at `http://127.0.0.1:8000/docs`, and the OpenAPI schema is available at `http://127.0.0.1:8000/openapi.json`.


### Test with Swagger UI `/docs`

Yes. After starting Uvicorn, open `http://127.0.0.1:8000/docs` in your browser. You can expand:

- `GET /api/prompts/route`, click **Try it out**, enter a prompt such as `Create a Python FastAPI backend`, and execute it.
- `POST /api/prompts/execute`, click **Try it out**, use a JSON body such as `{"prompt":"Process an invoice document"}`, and execute it.

The Swagger page is backed by `http://127.0.0.1:8000/openapi.json`.

### GET `/api/prompts/route`

Use this endpoint when the frontend has a prompt and wants to know which backend tool should handle it.

```bash
curl "http://127.0.0.1:8000/api/prompts/route?prompt=Create%20a%20Python%20FastAPI%20backend"
```

Example response:

```json
{
  "prompt": "Create a Python FastAPI backend",
  "category": "backend",
  "tool_name": "resolve_backend_skill",
  "reason": "Detected backend-generation intent."
}
```

### POST `/api/prompts/execute`

Use this endpoint when the frontend wants the API to execute the prompt by calling the inferred tool.

```bash
curl -X POST "http://127.0.0.1:8000/api/prompts/execute" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Process an invoice document"}'
```

You can also force a specific supported tool with `tool_name` and pass tool-specific `arguments`:

```bash
curl -X POST "http://127.0.0.1:8000/api/prompts/execute" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Create a document tool","tool_name":"generate_document_tool_spec","arguments":{"capability":"redact"}}'
```

Router validation is covered by unit tests and can be checked with:

```bash
python -m compileall src tests
pytest -q
```
