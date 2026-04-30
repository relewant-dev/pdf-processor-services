# AGENTS.md

This file defines contribution instructions for agents working in this repository.
Scope: entire repository (`/workspace/smart-ide-services`).

## Project goal
Build **Smart IDE Services**: backend services that power an AI-assisted IDE experience, starting with an MCP service that talks to local models via Ollama.

## Working principles
- Keep changes small, reversible, and production-oriented.
- Prefer explicit error messages and operational guidance for local dev.
- Preserve asynchronous I/O for networked code paths.
- Add or update docs when behavior, setup, or architecture changes.

## Tech stack (current)
- Python 3.10+
- FastMCP service runtime
- httpx for outbound HTTP
- Local Ollama for model inference

## Recommended project structure
Use this layout as the codebase grows:

```text
smart-ide-services/
├─ AGENTS.md
├─ README.md
├─ pyproject.toml
├─ src/
│  ├─ __init__.py
│  ├─ server.py                 # MCP server bootstrap
│  ├─ config.py                 # environment + settings
│  ├─ clients/
│  │  └─ ollama.py              # provider adapters
│  ├─ tools/
│  │  ├─ chat.py                # MCP tools
│  │  └─ health.py
│  ├─ prompts/
│  │  └─ templates.py
│  └─ domain/
│     └─ models.py
├─ tests/
│  ├─ unit/
│  └─ integration/
└─ docs/
   ├─ architecture.md
   ├─ api.md
   └─ runbooks/
```

## Coding guidelines
- Use type hints on all public functions.
- Keep functions focused; avoid large multi-purpose modules.
- Prefer dependency boundaries:
  - `clients/*` for external APIs.
  - `tools/*` for MCP tool wiring.
  - `domain/*` for business logic/data models.
- Do not put `try/except` around imports.

## Quality checks
Before finalizing changes, run relevant checks:
- `python -m compileall src`
- `pytest` (when tests exist)

## Commit and PR conventions
- Follow Conventional Commits (`feat:`, `docs:`, `fix:`, etc.).
- PRs should include:
  - what changed,
  - why it changed,
  - validation commands + results,
  - follow-up work (if any).

## Notes for future smart IDE features
When adding capabilities, prefer this order:
1. Reliable core chat and health primitives.
2. File/workspace tools (read, write, diff, search).
3. Code actions (explain, refactor, test generation).
4. Multi-file planning/execution orchestration.
5. Optional remote model/provider abstraction.
