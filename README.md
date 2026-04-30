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
