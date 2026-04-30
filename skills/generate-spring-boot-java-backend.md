# Skill: generate-spring-boot-java-backend

## Trigger
Use this skill when the user asks for Java backend generation, e.g. "Create a backend in Java".

## Goal
Generate a production-oriented Spring Boot backend scaffold and implementation plan.

## Guidelines
1. Use Java 21+ and Spring Boot 3.x.
2. Prefer layered architecture: `controller -> service -> repository -> domain`.
3. Add DTO validation with Jakarta Validation.
4. Add centralized exception handling (`@ControllerAdvice`).
5. Include health/readiness endpoints via Spring Actuator.
6. Add config profile strategy (`dev`, `test`, `prod`).
7. Include auth/security baseline (JWT + role checks).
8. Include testing baseline (unit + integration with Testcontainers if DB is used).

## Deliverables
- Project structure tree.
- Core dependencies.
- Initial endpoints (`/health`, `/api/v1/*`).
- Data model + migration strategy.
- Test plan and run commands.
