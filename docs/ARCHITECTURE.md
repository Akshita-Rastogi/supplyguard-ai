# Architecture and code navigation

```text
ui/app.py                         reviewer-facing Streamlit product
src/supplyguard/
  api/routes.py                   HTTP contracts, auth, feedback, health, metrics
  core/config.py                  environment-backed typed configuration
  core/logging.py                 centralized JSON logging
  core/middleware.py              correlation IDs, latency and request metrics
  domain/models.py                API and citation contracts
  evaluation.py                   answer completeness/grounding/refusal metrics
  ingestion/models.py             normalized page-element and chunk contracts
  ingestion/parsers.py            PDF/Markdown, tables, images, OCR/blank classification
  ingestion/chunker.py            page-aware overlapping semantic chunks
  infrastructure/mongo.py         native async PyMongo, records, feedback, audit, indexes
  infrastructure/ollama.py        local embedding/generation, timeout/retry/concurrency
  infrastructure/vector.py        Qdrant collections, payload filters and search
  infrastructure/mcp_client.py    Streamable HTTP MCP client boundary
  retrieval/hybrid.py             dense + lexical reciprocal-rank fusion
  services/router.py              guarded local-LLM intent selection and rule fallback
  services/analytics.py           safe allowlisted MongoDB computation
  services/contradictions.py      cross-evidence conflict warnings
  services/memory.py              bounded tenant-isolated conversation context
  services/orchestrator.py        use-case coordination and decision audit
  mcp_server.py                   independent FEMA MCP tools service
scripts/seed.py                   offline parse/embed/index pipeline
scripts/evaluate.py               measured golden-set report
scripts/benchmark_chunking.py      reproducible chunk-selection experiment
tests/                             unit, parser, vector isolation, MCP tool tests
requirements.txt                  application, test, and lint dependencies
pytest.ini                        minimal test configuration
```

## State boundaries

- **MongoDB:** heterogeneous business records, canonical chunk metadata, feedback, audit, ingestion runs, and TTL-limited session turns.
- **Qdrant:** dense vectors plus retrievable evidence payload. Tenant and metadata constraints are applied before candidate return.
- **Ollama:** local model runtime. `nomic-embed-text` creates vectors and `mistral:instruct` synthesizes from bounded evidence.
- **MCP service:** owns external-data tool semantics and reads the immutable FEMA snapshot. The API is an MCP client, not a direct CSV reader.

## Failure boundaries

Startup does not claim readiness unless MongoDB, Qdrant, Ollama, and the MCP service answer. Serving never falls back to ungrounded model knowledge when retrieval or generation fails. Tool failure is represented in the trace. Parsing failures are recorded in ingestion runs. Unexpected HTTP errors receive correlation IDs and generic client messages while internal logs retain error types.

## Key decisions

- MongoDB is the operational and audit store; Qdrant is the dedicated local vector index.
- Ollama keeps document content and inference local.
- Explicit orchestration plus a schema-constrained local classifier is easier to inspect than adding
  a graph framework for three execution routes and one unsupported/refusal outcome.
- Public feeds are versioned snapshots, so external outages and schema drift never silently change evaluation results.

## Important failure cases

- Invalid input or tenant IDs return validation errors before retrieval.
- Tenant filters are mandatory in both MongoDB and Qdrant.
- Empty/weak evidence produces refusal.
- Embedded PDF instructions remain untrusted evidence and cannot select tools.
- Missing telemetry is represented as unknown, never zero.
- Ollama/MCP/Qdrant failures produce explicit warnings without ungrounded fallback.
- Duplicate ingestion and feedback are idempotent.
- Image-only pages are marked for OCR; blank pages receive explicit audit markers.

## Security boundary

The demo uses API-key roles, scalar input contracts, server-built MongoDB pipelines, bounded model context and generic client errors. Production should replace demo keys with OIDC/JWT scopes, use managed secrets, encrypt backups, export audit records to immutable storage and continuously test indirect prompt injection and tenant isolation.
