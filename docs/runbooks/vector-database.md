# Vector database runbook

Smart IDE Services uses **Qdrant** for vector persistence. Qdrant stores the requested `candidates` and `insurances` data as dedicated vector collections, with the structured fields stored as payload and the PDF representation stored as the point vector.

## Collections

The `initialize_vector_database` MCP tool creates these Qdrant collections when they do not already exist:

- `candidates`: CV/resume extraction output written by `cv-reader-agent`.
- `insurances`: insurance-policy extraction output written by `insurance-document-reader-agent`.

Each collection uses cosine distance and `VECTOR_SIZE` dimensions. The relational-style fields from the original table request are preserved as Qdrant payload keys. The extracted PDF text is stored in `source_document_text` so operators can inspect the evidence behind each embedded point.

Candidate points use a deterministic UUID derived from `email` when an email is available, so reprocessing the same CV updates the same point. Insurance points use a deterministic UUID derived from `insurance_number`.

## Configuration

Environment variables:

- `QDRANT_URL`: Qdrant endpoint; defaults to `http://127.0.0.1:6333`.
- `QDRANT_API_KEY`: optional API key for secured Qdrant deployments.
- `QDRANT_TIMEOUT_SECONDS`: Qdrant client timeout; defaults to `30`.
- `OLLAMA_EMBEDDING_MODEL`: embedding model used by Ollama `/api/embed`; defaults to `nomic-embed-text`.
- `VECTOR_SIZE`: vector size expected by Qdrant collections; defaults to `768`, matching `nomic-embed-text`.

## Local setup

```bash
docker run -p 6333:6333 -p 6334:6334 qdrant/qdrant
ollama pull nomic-embed-text
QDRANT_URL=http://127.0.0.1:6333 python src/server.py
```

Then call `initialize_vector_database` once. After that:

- call `process_candidate_pdf` for CV/resume PDFs; it extracts structured candidate JSON, creates an embedding, and upserts into the `candidates` collection.
- call `process_insurance_pdf` for insurance PDFs; it extracts structured policy JSON, creates an embedding, and upserts into the `insurances` collection.

## Operational notes

- The PDF must contain extractable text. Scanned/image-only PDFs still need OCR before ingestion.
- `VECTOR_SIZE` must match the active Ollama embedding model and the existing Qdrant collection size. If it differs, persistence fails with an explicit dimension mismatch error before calling Qdrant.
- Extracted structured JSON is validated before writing to Qdrant, so invalid model output is rejected instead of partially stored.
