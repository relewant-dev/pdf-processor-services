# Skill: generate-fastapi-python-backend

## Trigger
Use this skill when the user asks for Python backend generation with FastAPI.

## Goal
Generate an async-first FastAPI backend scaffold and implementation plan.

## Guidelines
1. Use Python 3.11+ and FastAPI with pydantic models.
2. Use module boundaries: `routers`, `services`, `clients`, `domain`, `schemas`.
3. Prefer async I/O for network and DB paths.
4. Add health/readiness endpoints.
5. Add settings via environment-backed configuration.
6. Add auth/security baseline (JWT/OAuth2 scopes as needed).
7. Add structured logging and request IDs.
8. Include tests (pytest + httpx AsyncClient).

## Deliverables
- Project structure tree.
- Dependency list and app bootstrap.
- Starter routers and schema contracts.
- Observability/security checklist.
- Test plan and run commands.
