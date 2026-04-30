# Skill: generate-express-typescript-backend

## Trigger
Use this skill when the user asks for Node.js backend generation with Express/TypeScript.

## Goal
Generate a maintainable Express + TypeScript backend scaffold and plan.

## Guidelines
1. Use Node 20+ and strict TypeScript config.
2. Use modular layout: `routes`, `controllers`, `services`, `repositories`, `schemas`.
3. Use runtime validation (zod or equivalent).
4. Add centralized error middleware.
5. Add health endpoint and structured logging.
6. Ensure graceful shutdown and signal handling.
7. Include auth/security baseline (JWT, secure headers, rate limiting).
8. Include tests (unit + integration using supertest).

## Deliverables
- Project structure tree.
- package dependencies and scripts.
- API contract starter endpoints.
- Validation and error-handling strategy.
- Test plan and run commands.
