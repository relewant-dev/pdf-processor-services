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
- `src/tools/blueprints.py`: document-processing blueprint and routing tool logic.
- `src/domain/blueprints.py`: document-processing blueprint registry.
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
- insurance document-reading flow routing and agent/skill exposure;
- CV/resume reading flow routing and agent/skill exposure;
- invalid stack intent handling;
- blueprint list contains expected generation skills.

## Insurance document-reading agent

Document-processing blueprints include an `insurance-document-reader-agent` for reading insurance policies and related claim documents. Insurance prompts such as “read this insurance policy,” “summarize coverage,” “check exclusions,” or “extract claim requirements” route to the `insurance_policy_reading` flow and use these skills:

- `insurance-policy-reading`
- `coverage-exclusions-analysis`
- `claims-requirements-extraction`

The insurance agent summarizes policy facts, coverage, exclusions, deadlines, and claim obligations from supplied document text, while flagging missing pages, ambiguous clauses, and items needing licensed or legal review.


## CV/resume document-reading agent

Document-processing blueprints include a `cv-reader-agent` for reading CVs, resumes, academic CVs, and candidate profiles. CV prompts such as “read this CV,” “summarize this resume,” or “extract candidate skills” route to the `cv_reading` flow and use these skills:

- `cv-reading`
- `candidate-profile-extraction`
- `experience-skills-normalization`

The CV reader agent extracts evidence-backed candidate facts, timelines, education, certifications, projects, skills, and review warnings from supplied document text while protecting PII and avoiding unsupported hiring decisions. Persisted candidate payloads keep `education` as a list of obtained degrees, `certification` as a list of earned certifications, and `languages` as a list of candidate languages.

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

The HTTP API exposes prompt execution plus PDF upload endpoints. For prompts, the frontend sends only the user message in the JSON body as `{"message":"prompt"}`; the service routes that message to the correct document, health, or general chat tool, uses the inferred tool and related skills as Ollama context when applicable, and returns only the model answer as `{"response":"result of the prompt"}`. For PDFs, the frontend sends `multipart/form-data` with a PDF file and question, and receives an Ollama answer based on the uploaded document content.

### Run the HTTP API locally

Install the project dependencies, then start Uvicorn from the repository root using the same Python environment:

```bash
python -m pip install -e .
python -m uvicorn http_api:app --app-dir src --reload
```

Using `python -m uvicorn` helps avoid accidentally running a globally installed Uvicorn that cannot see this project's installed dependencies. If startup reports a missing HTTP API dependency such as `starlette` or `multipart`, reinstall the project dependencies in the Python environment that launches Uvicorn:

```bash
python -m pip install -e .
```

A route summary is available at `http://127.0.0.1:8000/`. Swagger UI is available at `http://127.0.0.1:8000/docs`, and the OpenAPI schema is available at `http://127.0.0.1:8000/openapi.json`.


### Test with Swagger UI `/docs`

Yes. After starting Uvicorn, open `http://127.0.0.1:8000/docs` in your browser. You can expand:

- `POST /api/documents/pdf`, click **Try it out**, choose a PDF file, enter a `question`, and execute it.
- `POST /api/prompts/execute`, click **Try it out**, use a JSON body such as `{"message":"Process an invoice document"}`, and execute it.

The Swagger page is backed by `http://127.0.0.1:8000/openapi.json`.

### POST `/api/documents/pdf`

Use this endpoint when the frontend needs to upload a PDF with `multipart/form-data` and ask a question about the document content. The API extracts text from the PDF first, then sends that extracted text to Ollama. Ollama does **not** read the raw PDF binary directly. Scanned or image-only PDFs need OCR before this endpoint can answer questions from their content.

The form fields are:

- `file`: required PDF upload.
- `question`: required question to answer from the PDF content.
- `max_chars`: optional maximum extracted characters to include in the model prompt; defaults to `30000`.

```bash
curl -X POST "http://127.0.0.1:8000/api/documents/pdf" \
  -F "file=@/path/to/document.pdf;type=application/pdf" \
  -F "question=Summarize this document" \
  -F "max_chars=30000"
```

Successful responses contain only the Ollama answer as `{"response":"result based on the uploaded PDF"}`.

When the uploaded text is classified as a CV/resume or insurance policy, the service also upserts a Qdrant payload in the configured `candidates` or `insurances` collection. In addition to `raw_text`, the persistence layer maps detected CV sections into candidate fields such as `education`, `previous_works`, and `competences`, and maps detected insurance policy facts into `coverage_details`, `documents`, `provider_name`, `insurance_number`, `insurance_type`, and `status`. Missing fields remain empty or `unknown` instead of being guessed.

### POST `/api/prompts/execute`

Use this endpoint when the frontend wants the API to route a user message and execute it by calling the inferred tool.

```bash
curl -X POST "http://127.0.0.1:8000/api/prompts/execute" \
  -H "Content-Type: application/json" \
  -d '{"message":"Process an invoice document"}'
```

The router chooses the tool from the message content. The request body must contain only the `message` field, and successful responses contain only the `response` field with the Ollama model result.

Router validation is covered by unit tests and can be checked with:

```bash
python -m compileall src tests
pytest -q
```


## Docker Compose (Qdrant storage path from `.env`)

A Docker Compose file is included at the repository root and reads the Qdrant host storage path from `.env` using `QDRANT_STORAGE_PATH`.

Current `.env` example:

```bash
QDRANT_STORAGE_PATH=./qdrant_storage
```

Start Qdrant with:

```bash
docker compose up -d qdrant
```

