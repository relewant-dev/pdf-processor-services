# SKILL.md

This folder contains reusable backend-generation skills for MCP intent routing.

## Available skills

1. `generate-spring-boot-java-backend`
   - Trigger: requests like "Create a backend in Java" or "Create a Spring Boot API".
   - Outcome: Spring Boot scaffold guidelines, architecture, security, and testing baseline.

2. `generate-express-typescript-backend`
   - Trigger: requests like "Create a Node backend with Express and TypeScript".
   - Outcome: Express + TypeScript scaffold guidelines, validation, middleware, and tests.

3. `generate-fastapi-python-backend`
   - Trigger: requests like "Create a backend in Python with FastAPI".
   - Outcome: FastAPI async-first scaffold guidelines, schema contracts, and tests.

## Routing guidance

- Java/Spring intent -> `generate-spring-boot-java-backend`
- Node/Express/TypeScript intent -> `generate-express-typescript-backend`
- Python/FastAPI intent -> `generate-fastapi-python-backend`

## Usage contract

- Keep skills focused on production-oriented backend scaffolding.
- Include architecture, security, observability, and testing guidance.
- Keep stack-specific conventions explicit and actionable.
