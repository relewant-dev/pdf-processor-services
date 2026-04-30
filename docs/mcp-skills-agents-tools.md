# MCP Skill, Agent, and Tool Blueprint (Backend-Focused)

This document defines a starter catalog of **skills**, **agents**, and **MCP tools** aligned to your backend stacks:

- Java (Spring Boot)
- Node.js (Express + TypeScript)
- Python (FastAPI)

## 1) Skill catalog

Skills are reusable capability bundles (instructions + workflows + guardrails).

### Cross-stack core skills

1. **api-design**
   - Define REST resources, status codes, pagination, filtering, and error contracts.
2. **auth-security**
   - JWT/session handling, RBAC checks, OWASP validations, secrets handling.
3. **data-modeling**
   - Entity/schema design, migrations, indexing strategy, validation constraints.
4. **testing-strategy**
   - Unit/integration/e2e test design with fixture and mocking patterns.
5. **observability**
   - Logging, tracing, metrics, health/readiness/liveness standards.

### Java Spring Boot skills

1. **spring-api-implementation**
   - Controllers, services, DTO mapping, validation, exception handlers.
2. **spring-data-jpa**
   - Repository methods, transaction boundaries, query optimization.
3. **spring-boot-hardening**
   - Profiles, config properties, actuator, resilience and retry patterns.

### Node.js (Express + TypeScript) skills

1. **express-route-architecture**
   - Route-module boundaries, middleware order, error propagation.
2. **typescript-domain-modeling**
   - Types/interfaces/zod schemas and runtime validation strategy.
3. **node-runtime-reliability**
   - Process signals, graceful shutdown, async error handling, backpressure.

### Python FastAPI skills

1. **fastapi-endpoint-design**
   - Router structure, pydantic models, dependency injection.
2. **fastapi-async-io**
   - Async path operations, clients, timeouts, cancellation-safe patterns.
3. **python-service-operations**
   - Settings management, startup checks, worker deployment conventions.

## 2) Agent catalog

Agents are role-specialized planners/executors that compose skills.

1. **backend-architect-agent**
   - Input: feature requirements.
   - Output: service boundaries, module layout, contracts per stack.
   - Uses: `api-design`, `data-modeling`, `observability`.

2. **spring-implementation-agent**
   - Input: Java feature ticket.
   - Output: Spring controller/service/repository patch plan.
   - Uses: `spring-api-implementation`, `spring-data-jpa`, `testing-strategy`.

3. **express-ts-implementation-agent**
   - Input: Node feature ticket.
   - Output: route/service/schema/middleware plan.
   - Uses: `express-route-architecture`, `typescript-domain-modeling`, `testing-strategy`.

4. **fastapi-implementation-agent**
   - Input: Python feature ticket.
   - Output: router/service/schema/dependency plan.
   - Uses: `fastapi-endpoint-design`, `fastapi-async-io`, `testing-strategy`.

5. **backend-review-agent**
   - Input: diff/PR summary.
   - Output: correctness, security, and operability review comments.
   - Uses: `auth-security`, `observability`, `testing-strategy`.

## 3) MCP tool catalog (implementation targets)

The following tools are designed to be exposed by the MCP server.

1. `list_backend_blueprints`
   - Returns supported stacks and available skills/agents.

2. `generate_skill_set`
   - Inputs: `stack`, `project_type`.
   - Returns prioritized skills with rationale and checklist.

3. `generate_agent_plan`
   - Inputs: `stack`, `feature_summary`, `constraints`.
   - Returns multi-step execution plan and handoff points.

4. `generate_tool_spec`
   - Inputs: `stack`, `capability`.
   - Returns MCP tool contract (name, args schema, return schema, error guidance).

5. `generate_backend_scaffold_tasks`
   - Inputs: `stack`, `architecture_style`, `db_choice`.
   - Returns scaffold task list for bootstrapping a new service.

## 4) Suggested first workflow

1. Call `list_backend_blueprints`.
2. Call `generate_skill_set` for selected stack.
3. Call `generate_agent_plan` for the first feature.
4. Call `generate_tool_spec` for missing MCP capabilities.
5. Execute scaffold tasks from `generate_backend_scaffold_tasks`.
