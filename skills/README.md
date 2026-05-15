# Skills Catalog

This directory contains reusable skills for stack-specific backend generation:

- `generate-spring-boot-java-backend`
- `generate-express-typescript-backend`
- `generate-fastapi-python-backend`

It also contains reusable document-processing skills:

- `document-classification`
- `ocr-extraction`
- `structured-data-mapping`
- `pii-redaction`
- `document-validation`
- `fraud-signals-detection`
- `insurance-policy-reading`
- `coverage-exclusions-analysis`
- `claims-requirements-extraction`
- `document-processing-observability`

## Intent routing examples
- "Create a backend in Java" -> `generate-spring-boot-java-backend`
- "Create a Node backend with Express and TS" -> `generate-express-typescript-backend`
- "Create a backend in Python using FastAPI" -> `generate-fastapi-python-backend`


## Insurance document reading

Insurance-related prompts such as “read this insurance policy,” “summarize coverage,” or “extract claim requirements” should route to the document-processing blueprint and use the `insurance-document-reader-agent` with these skills:

- `insurance-policy-reading` for policy declarations, endorsements, limits, deductibles, exclusions, and renewal/cancellation terms.
- `coverage-exclusions-analysis` for mapping user scenarios to coverage grants, limits, exclusions, exceptions, and ambiguous clauses.
- `claims-requirements-extraction` for notice duties, proof-of-loss requirements, evidence checklists, deadlines, and escalation paths.
