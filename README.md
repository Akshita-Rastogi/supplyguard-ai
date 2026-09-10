# SupplyGuard AI

SupplyGuard AI is a local question-answering assistant built for the AI Engineer assessment. It answers questions from long PDF documents, computes answers from a CSV, calls an external tool through MCP, cites its evidence, records feedback, and refuses when it does not have enough evidence.

I chose a procurement and supply-chain risk use case because it exercises all three reasoning paths in one coherent domain:

- World Bank and NIST PDFs provide complex document questions.
- OpenFEMA disaster declarations provide structured-data questions.
- A separate FEMA MCP server demonstrates tool selection and tool execution.

The assessment asks for a small dataset and a lightweight application. I intentionally used a larger public corpus to demonstrate that the same simple design still works with long documents, tables, figures, acronyms, blank pages and more than 70,000 CSV rows. The application remains local and does not require cloud deployment, fine-tuning or a paid API.

## Submission artifacts

- `docs/SupplyGuard_AI_Architecture.drawio` is the editable end-to-end architecture and flow diagram.
- `docs/SupplyGuard_AI_Architecture.png` is the high-resolution submission-ready diagram export.
- `output/submission/SupplyGuard_AI_Assessment_Submission.pdf` is the reviewer-ready submission report.
- `output/submission/SupplyGuard_AI_Assessment_Submission.docx` is the editable version of the report.

## What is included

| Assessment capability | Implementation |
|---|---|
| Questions from documents | Page-aware RAG over three official PDFs |
| Structured-data questions | MongoDB aggregation over the official FEMA CSV |
| External tool | MCPServer (MCP 2.x, with v1 fallback) exposing FEMA tools |
| Grounded answers | Ollama receives only the retrieved evidence packet |
| Citations | Source title, PDF page, element type, chunk number, excerpt and score |
| Uncertainty | Retrieval threshold and explicit refusal |
| Feedback | Helpful/not-helpful stored against the request ID |
| Conversational context | Bounded, tenant-isolated session memory with a New chat control |
| Evaluation | 8 required cases plus 6 additional difficult cases |
| Interface | Streamlit chat, evidence, tool trace, health and evaluation views |

## Dataset

Only files downloaded from official public sources are used. There are no invented policy files or synthetic business records in `data/`.

| Source | Format and size | Why I selected it |
|---|---|---|
| World Bank Procurement Regulations, September 2025 | PDF, 154 pages | Rules, annexes, headings and procurement terminology |
| World Bank Contract Management Guidance, 2024 | PDF, 124 pages | Tables, diagrams, contract workflows, KPIs and risk guidance |
| NIST SP 800-161 Rev. 1 Update 1 | PDF, 325 pages | Dense control tables, acronyms, cross-references and supply-chain risk practices |
| OpenFEMA Disaster Declarations v2 | CSV, 70,402 rows | Dates, null values, geographic codes, incident types and real aggregation questions |

Official source URLs and checksums are recorded in `docs/DATA_MANIFEST.md`. The downloaded copies are kept in the repository so ingestion and evaluation are reproducible even if an upstream website changes.

## Architecture

```text
                         +----------------------+
                         |     Streamlit UI     |
                         +----------+-----------+
                                    |
                                    v
                         +----------------------+
                         |       FastAPI        |
                         | auth, validation,    |
                         | logs, memory, audit  |
                         +----------+-----------+
                                    |
                         guarded hybrid intent router
                +-------------------+-------------------+
                |                   |                   |
                v                   v                   v
        Document question    Structured question    MCP/tool question
                |                   |                   |
      Ollama query embedding   MongoDB aggregation   MCPServer process
                |                   |                   |
      Qdrant dense retrieval        |            Local FEMA CSV
      + Mongo lexical retrieval     |                   |
                |                   |                   |
            RRF fusion              |              Tool result
                |                   |                   |
      threshold + conflict check    |                   |
                |                   |                   |
       Ollama grounded answer       |                   |
                +-------------------+-------------------+
                                    |
                       answer + citations + tool trace
                                    |
                  MongoDB audit + feedback + session turns
```

I kept the orchestration explicit rather than adding LangChain or LangGraph. There are three execution
routes plus an unsupported/refusal outcome, so a small typed orchestrator is easier to explain,
debug and test. A graph framework would become useful if the system later required resumable
workflows, parallel tools or human approval checkpoints.

## Why Ollama and these models?

All inference runs locally through Ollama. This avoids API cost, external rate limits and sending assessment documents to a third party.

### Generation model: `mistral:instruct`

I evaluated the models already installed on the machine: `llama2`, `openchat` and `mistral:instruct`. I selected `mistral:instruct` because this task is instruction-heavy: the model must stay inside supplied evidence, retain citations and refuse unsupported questions. It is also small enough to run locally on a laptop without turning the assessment into an infrastructure exercise.

Generation uses:

- temperature `0` for repeatability;
- a maximum of 500 generated tokens;
- a maximum evidence packet of 12,000 characters;
- at most four concurrent Ollama requests;
- connection and response timeouts;
- one retry for a transient connection failure.

The prompt explicitly says that retrieved documents are untrusted evidence, not instructions. If Ollama fails or returns an empty response, the assistant does not fall back to unsupported model knowledge.

### Embedding model: `nomic-embed-text`

I installed `nomic-embed-text` because it is designed specifically for semantic retrieval and works through the same local Ollama runtime. It produces 768-dimensional vectors. A dedicated embedding model is more appropriate than taking hidden states from the generation model because it is smaller, faster and trained for similarity search.

The embedding model name is configuration, and the Qdrant collection name includes a version. If the embedding model changes, I would create a new collection and reindex rather than mix incompatible vector spaces.

## Why Qdrant for the vector database?

MongoDB remains the operational database, accessed through PyMongo's native asynchronous client, but local MongoDB Community does not provide the same vector-search capability as MongoDB Atlas. I did not want the local code to pretend that an Atlas-only index existed.

I considered three choices:

1. FAISS is simple and fast, but metadata filtering, persistence and concurrent service access require additional application code.
2. Chroma is convenient for prototypes, but Qdrant gives clearer collection management, payload indexes and filtering behavior.
3. Qdrant provides persistent cosine-vector search, Docker support and server-side tenant/metadata filters while remaining lightweight.

For this reason, Qdrant stores embeddings and retrieval payloads. MongoDB stores canonical chunk metadata, structured FEMA records, feedback, audit events and ingestion runs. The separation makes each database responsibility clear.

## Document ingestion

Ingestion is an offline step performed by `scripts/seed.py`:

1. Read only `data/documents/public/*.pdf`.
2. Open each PDF with PyMuPDF.
3. Extract page text in reading order.
4. Detect and serialize tables separately so rows are not lost inside page prose.
5. Count images and identify pages that require OCR.
6. Mark blank or non-extractable pages instead of silently dropping them.
7. Split each page element into chunks.
8. Generate local embeddings with Ollama.
9. Store canonical chunks in MongoDB and vectors in Qdrant.
10. Record an ingestion-run summary and any parser failures.

Each chunk receives:

- a deterministic source ID;
- a deterministic Qdrant point UUID;
- source title;
- PDF page number;
- element type (`text`, `table`, `ocr_required` or `blank_page`);
- chunk number;
- content checksum;
- tenant ID and parsing metadata.

Deterministic IDs make ingestion idempotent: running the seed script again updates the same records instead of creating duplicates.

## Chunking strategy

The implemented chunk size is **160 words with 30 words of overlap**. The step size is therefore 130 words. I selected it after running `scripts/benchmark_chunking.py` over all three PDFs and the four golden document questions—not by choosing a conventional value and justifying it afterwards.

| Candidate | Chunks | Concept recall@6 | Hit rate@6 | MRR@6 | Mean lexical latency | Mean context words |
|---|---:|---:|---:|---:|---:|---:|
| **160/30 (selected)** | 2,198 | **74.6%** | 100% | 0.413 | 83.4 ms | **749** |
| 240/40 | 1,562 | 70.5% | 100% | 0.396 | 75.8 ms | 1,067 |
| 400/60 | 1,114 | 74.1% | 100% | **0.479** | **70.3 ms** | 1,434 |

The measurements are an offline lexical retrieval proxy, not a claim about end-to-end answer accuracy. `concept recall@6` measures how many expected-answer concepts appear in the top six chunks; `hit rate@6` checks whether every question retrieved at least one relevant chunk; `MRR@6` rewards placing the first relevant chunk near rank one; latency measures the ranking pass; context words estimate the generation cost. Exact values are stored in `chunking_benchmark.csv` and can be regenerated with `PYTHONPATH=src python scripts/benchmark_chunking.py`.

I chose this after considering the document structure:

- These PDFs contain long policy paragraphs and control descriptions. Very small chunks often separate a requirement from its exception or explanatory sentence.
- Very large chunks reduce retrieval precision and consume too much of the local model context.
- The 160-word candidate achieved the highest concept recall and smallest generated context packet in this corpus.
- A 30-word overlap carries headings, sentence endings and cross-boundary conditions into the next chunk without the duplication cost of a larger overlap.
- Chunking happens inside each page element, so a chunk never silently combines unrelated pages.
- Tables are chunked separately from narrative text. This prevents a large table from distorting the surrounding paragraph representation.

The selection is a trade-off. The 400-word candidate produced the best MRR and lowest ranking latency, but its top-six packet was 91% larger than 160/30, reducing evidence focus and leaving less local-model context for conversation and output. The selected candidate creates 39% more vectors than 240/40, but the additional storage is acceptable for this corpus because it gained four percentage points of concept recall. The benchmark should be rerun whenever the corpus, parser, embedding model, or evaluation questions change.

## Retrieval strategy

I use hybrid retrieval because the documents contain both semantic concepts and exact terminology.

### Dense retrieval

The question is embedded with `nomic-embed-text`. Qdrant retrieves the top 20 cosine-similarity candidates after applying tenant and metadata filters.

Dense retrieval is useful for paraphrases. For example, a user may ask about “vendor checking” while the NIST document uses “supplier due diligence”.

### Lexical retrieval

MongoDB supplies up to 20 lexical candidates using normalized term-frequency cosine scoring. This path helps exact acronyms, control identifiers, monetary values and uncommon procurement terms.

### Reciprocal-rank fusion

The two ranked lists are combined using Reciprocal Rank Fusion:

```text
RRF score(document) = sum(1 / (60 + rank_in_each_list))
```

I chose RRF because dense and lexical scores have different numeric scales. Combining raw scores would require calibration. RRF uses rank instead, is stable with small candidate lists and rewards chunks found by both retrieval methods.

The final top **6** chunks are returned. Six gives the generator enough evidence for cross-document questions without flooding a small local model with loosely related text. The API exposes every selected citation and normalized fused score.

## Grounded answer generation and citations

The generator receives a bounded packet shaped like:

```text
[S1] Source title (page:12:text:chunk:0)
Retrieved evidence...

[S2] Source title (page:88:table:chunk:1)
Retrieved evidence...
```

The model is required to answer only from this packet and cite labels such as `[S1]`. The response object also contains structured citations, so the UI can show the actual excerpt, page locator and retrieval score even if model prose is imperfect.

This separation matters: a citation is not considered valid merely because the model prints a source-looking string. The application already knows which chunks were retrieved and returns them independently.

## Structured CSV questions

The FEMA CSV is parsed during seeding and stored as typed MongoDB records. `disasterNumber` and `fyDeclared` are converted to integers; the remaining source fields are preserved.

Structured questions never go through the LLM for arithmetic. The service builds a server-owned aggregation pipeline:

```text
match tenant + FEMA record type + optional year
group by the requested dimension plus disasterNumber
count distinct disaster declarations
sort descending
limit to one result or top five
```

Supported examples include:

- Which state has the most disaster declarations? (Counts distinct
  `disasterNumber` values; OpenFEMA repeats disasters across designated-area rows.)
- Show the top incident types by declarations in 2025.
- Which region has the highest declaration count?

The user cannot send raw MongoDB operators or arbitrary pipelines. This prevents NoSQL injection and ensures the final number comes from actual computation.

## Tool calling and MCP

The external tool is a separate MCPServer using the Streamable HTTP transport. The implementation
uses the current MCP 2.x `MCPServer` and first-class `Client` APIs, with a narrow import fallback for
MCP 1.x because dependencies are intentionally unpinned. It exposes:

### `disaster_statistics`

Inputs:

- optional two-letter state code;
- optional four-digit year.

Output:

- applied filters;
- total distinct disaster declarations;
- matching designated-area row count for grain transparency;
- counts grouped by incident type;
- source name.

### `lookup_disasters`

Inputs:

- required two-letter state code;
- optional incident type;
- result limit constrained to 1–50.

Output:

- total matches;
- newest matching FEMA records;
- source name.

The MCP server reads the local official CSV and owns the tool schema and validation. The FastAPI service is a real MCP client: it establishes a session, initializes it and invokes the selected tool.

### How the assistant decides to call MCP

The router is hybrid and explainable. It has four typed outcomes: `document`, `analytics`,
`live_risk`, and `unsupported`:

- explicit phrases such as `use the FEMA tool`, `MCP tool` or `live disaster risk` select MCP
  deterministically, so a probabilistic classifier cannot ignore a direct tool instruction;
- other questions are sent to local `mistral:instruct` with a strict JSON schema whose only valid
  values are `document`, `analytics`, `live_risk`, and `unsupported`;
- invalid JSON, an unknown label, timeout, or Ollama outage activates the deterministic keyword
  fallback rather than failing the request.
- analytics requires both a FEMA subject and a supported computation phrase before MongoDB is
  accessed. Identity, personal-data, secret, unrelated live-data, and cross-tenant requests are
  refused without retrieval, aggregation, or tool execution.

This handles natural variations better than substring or fuzzy-string matching while retaining a
reliable path during model failure. Temperature zero and a 20-token output limit keep the routing
call small. The tool trace records the selected intent and strategy (`ollama`, `explicit_rule`, or
`rule_fallback`), making misrouting diagnosable. The trade-off is one extra local model call for
non-explicit questions; routing latency should therefore be measured separately from retrieval and
generation latency.

The final response includes a tool trace with the tool name, validated arguments, source and result count. If the MCP server is unavailable or returns invalid JSON, the assistant reports tool failure and does not fabricate an answer.

## Reliability and uncertainty

The primary reliability mechanism is a **retrieval confidence threshold of 0.35** after RRF normalization.

If no chunks are returned, embeddings fail, or the fused confidence is below the threshold, the assistant responds:

> I don't know based on the available evidence. Add a relevant source or narrow the question.

The displayed confidence is retrieval confidence, not a calibrated probability that the answer is factually correct. Calling it “answer accuracy” would be misleading.

Additional safeguards include:

- tenant filtering in both Qdrant and MongoDB;
- prompt instructions that treat retrieved text as untrusted data;
- allowlisted computation fields and server-generated aggregation pipelines;
- typed request and response contracts;
- bounded evidence and output size;
- dependency readiness checks;
- safe failure when Ollama, Qdrant, MongoDB or MCP is unavailable;
- no document bodies or secrets in application logs.

### Refusal demonstration

Question:

```text
What is the World Bank procurement director's home address?
```

Expected behavior: the corpus contains no reliable evidence for a private home address, so the assistant must refuse instead of answering from model memory.

## Feedback loop

After every response, Streamlit displays Helpful and Not Helpful controls. Feedback is upserted in MongoDB using the request ID, together with an optional reason and the actor role.

### Is this reinforcement learning or RLHF?

No. Recording a thumbs-up or thumbs-down does not change model weights, a reward model, a policy or even the prompt. It is an explicit product-quality signal.

It could later be used safely through an offline process:

1. Review and label feedback rather than trusting it automatically.
2. Join it with the stored question, answer, citations and tool trace.
3. Identify retrieval misses, poor answers and incorrect routing separately.
4. Add verified failures to the golden evaluation set.
5. Create hard-negative retrieval examples or improve prompts.
6. Run offline regression tests before deploying any change.

Calling the current implementation RLHF would overstate what it does.

## Context and session-memory management

I added conversational memory because real users rarely repeat every noun and filter in a
follow-up. After asking `Use the FEMA tool for CA in 2025`, the user can ask `What about
2024?` and the service can recover the missing state from the same conversation.

This is deliberately **session context**, not an unsupported claim that the model has learned
or developed permanent memory:

1. Streamlit creates a random `conversation_id` and sends it with every question.
2. After a successful response, the API stores the original question and answer in MongoDB.
3. On the next request, MongoDB loads at most the six most recent turns for the exact
   `tenant_id + conversation_id` pair.
4. A conservative follow-up detector only attaches history for short referential questions such
   as `What about 2024?`, `And which type?`, or `How about that state?`. A new standalone
   question is routed without old context, which reduces topic contamination.
5. The context packet is capped at 4,000 characters. If it grows beyond that boundary, the oldest
   content is removed while the current question and newest context are preserved.
6. The resolved question then follows the normal RAG, MongoDB analytics, or MCP path. Conversation
   text helps resolve intent and missing parameters, but it is explicitly labelled as context—not
   factual evidence. Document answers still require retrieved citations.
7. The tool trace reports how many memory turns were used, and the audit event records the
   conversation ID and memory count for debugging.
8. `New chat` creates a fresh ID and clears Streamlit's displayed history. MongoDB also applies a
   24-hour TTL to stored turns, so abandoned sessions expire automatically.

The boundaries are intentional. Memory is tenant-isolated, conversation IDs are validated, raw
history is never written to application logs, and a MongoDB memory failure degrades to a standalone
question instead of failing the whole answer. The number of turns, character budget and TTL are
environment settings (`MEMORY_MAX_TURNS`, `MEMORY_MAX_CHARS`, `MEMORY_TTL_HOURS`).

I would not send the entire chat transcript on every request. That increases latency, allows stale
topics to influence routing, and can eventually overflow a local model's context window. For a
longer-lived assistant, the next step would be a separately labelled, user-controlled summary with
deletion controls—not silently retaining unlimited chat history.

## Additional features added for stronger engineering evidence

These are deliberate extensions beyond the minimum assessment.

### 1. Hybrid retrieval with inspectable RRF

Dense retrieval handles semantic paraphrases; lexical retrieval protects exact terms and identifiers. The fusion logic is a small visible function rather than hidden framework behavior.

### 2. Replayable decision audit

Every request stores the actor, tenant, question, route, answer, citations, confidence, warnings and tool trace. This makes a wrong answer diagnosable: I can determine whether the failure came from routing, retrieval, generation or a tool.

### 3. Mixed-content and failure-aware ingestion

Text and tables are indexed separately. Image-only and blank pages are explicitly classified. Parser failures are stored in an ingestion-run record rather than silently ignored. This is useful for real enterprise document estates where “PDF” does not imply clean machine-readable text.

### 4. Bounded conversational memory

Follow-up questions can reuse recent context without mixing tenants, treating chat history as
evidence, or growing the prompt without a limit. Memory usage is visible in the tool trace and
automatically expires.

The project also includes structured JSON logging, correlation IDs, Prometheus request/latency metrics, health endpoints and idempotent ingestion. These are kept compact so they support the assessment rather than dominate it.

## Evaluation

`evaluation.json` contains the required assessment split followed by six bonus cases:

| Group | Count | Coverage |
|---|---:|---|
| Document | 4 | World Bank and NIST questions |
| Structured data | 2 | MongoDB computation over FEMA CSV |
| Tool calling | 1 | MCP FEMA statistics |
| Refusal | 1 | Unsupported private information |
| Bonus | 6 | Cross-document, table, acronym, adversarial, tenant isolation and unsupported identity |

Run:

```bash
docker compose exec api python scripts/evaluate.py
```

The script calls the running API and creates
`output/evaluation/evaluation_results.csv` with these columns:

| Metric | Meaning | Acceptance rule |
|---|---|---|
| Completeness | Fraction of expected-answer concepts present in the answer | At least 0.50 |
| Groundedness | Fraction of meaningful answer terms supported by returned citation excerpts | At least 0.50 for document cases |
| Citation coverage | Fraction of returned evidence items referenced using `[S#]` labels | Reported for diagnosis |
| Refusal correctness | Whether refusal/non-refusal matches the case type | Exactly 1.00 |
| Pass/Fail | Applies the relevant quality gate for that route | Completeness + groundedness for documents; completeness + refusal correctness otherwise |

These are deterministic proxy metrics, not an LLM judge and not a calibrated factual-accuracy
probability. Completeness catches answers that are correct but omit key requested points.
Groundedness catches fluent additions that do not appear in the retrieved evidence. Citation coverage
shows whether the model actually connected its prose to evidence labels. Refusal correctness ensures
that safety does not become either hallucination or indiscriminate refusal.

I use 0.50 as a visible baseline gate because the small golden set contains multi-part expected
answers and lexical variants. It is intentionally not described as “excellent” or “production
ready.” A score is good only when it clears the gate consistently across repeated runs and manual
inspection confirms that the lexical proxy has not been gamed. For structured and MCP questions, I
would additionally use numeric exact match in a larger evaluation set.

I do not commit invented generation scores when the API is not running. Execute
`docker compose exec api python scripts/evaluate.py` after starting and seeding the stack; each
result row then contains the
actual answer and all four measured scores. At the time of the documented chunking run, the API and
Ollama daemon were stopped, so only the reproducible chunking measurements above are reported as
completed results. This distinction prevents an unavailable dependency from being represented as a
successful model evaluation.

Automated unit tests cover routing, structured aggregation construction, request validation, contradiction detection, PDF table/image parsing, deterministic tenant-specific chunk IDs, Ollama failure handling, Qdrant tenant isolation and MCP computation.

## Logging and observability

All application logs are structured JSON. A request middleware creates or accepts an `X-Request-ID`, binds it to the logging context, records status and duration, returns it to the caller and updates Prometheus counters/histograms.

Health endpoints:

- `/health/live`: confirms the process is alive.
- `/health/ready`: checks MongoDB, Qdrant, Ollama and MCP reachability independently.
- `/metrics`: Prometheus request count and latency metrics.

Expected failures are represented as explicit responses and warnings. Unexpected failures return a generic error to the client while logging the request path and error type internally.

## Project structure

```text
supplyguard-ai/
├── data/
│   ├── documents/public/       # three official PDFs only
│   └── raw/public/             # official FEMA CSV only
├── docs/                       # architecture, rubric map, sources, demo guide
├── scripts/
│   ├── seed.py                 # parse, embed and index
│   ├── benchmark_chunking.py   # compare chunk candidates over the PDFs
│   └── evaluate.py             # score live generated answers
├── src/supplyguard/
│   ├── api/                    # FastAPI routes
│   ├── core/                   # config, logging, middleware
│   ├── domain/                 # typed contracts
│   ├── infrastructure/         # MongoDB, Qdrant, Ollama, MCP client
│   ├── ingestion/              # parsers and chunking
│   ├── retrieval/              # hybrid retrieval and RRF
│   ├── services/               # routing, analytics and orchestration
│   ├── main.py                 # API application
│   └── mcp_server.py           # independent MCP server
├── tests/
├── ui/app.py                   # Streamlit application
├── evaluation.json
├── chunking_benchmark.csv      # measured chunk-selection results
├── requirements.txt
├── pytest.ini
├── Dockerfile
└── docker-compose.yml
```

## Running the project

### Prerequisites

- Python 3.11 or newer
- Docker with Docker Compose
- Ollama running on the host

The project expects these local models:

```bash
ollama pull mistral:instruct
ollama pull nomic-embed-text
ollama serve
```

### Start services

The Compose file currently pins MongoDB 8.0.4 because MongoDB's newer builds refuse to start on
Docker Desktop Linux kernels in the affected 6.19–7.0.13 range (`SERVER-121912`). This is a local
runtime compatibility pin, not a recommendation to run an old patch in production. On a supported
kernel, use a current patched MongoDB release and validate the upgrade before changing the persisted
volume.

```bash
cp .env.example .env
docker compose up --build -d
docker compose ps
curl -i http://localhost:8000/health/ready
docker compose exec api python scripts/seed.py
```

Run the seed only after readiness reports HTTP 200. The first seed processes 603 PDF pages and
70,402 CSV rows. FEMA upserts are batched in groups of 1,000; document embeddings are batched in
groups of 16 and Qdrant writes in groups of 128. Subsequent runs are idempotent.

Open:

- Streamlit UI: `http://localhost:8501`
- FastAPI documentation: `http://localhost:8000/docs`
- API readiness: `http://localhost:8000/health/ready`
- MCP endpoint: `http://localhost:8001/mcp`
- Qdrant dashboard: `http://localhost:6333/dashboard`

### Verify persistent storage

Both databases use named Docker volumes: `mongo_data` and `qdrant_data`. Normal container restarts
and `docker compose down` preserve them. Only `docker compose down -v` deletes both volumes.

Use the authenticated inspection endpoint after seeding:

```bash
curl -s http://localhost:8000/v1/storage/stats \
  -H 'X-API-Key: demo-key' | python -m json.tool
```

It reports MongoDB counts for chunks, structured records, ingestion runs, audits, feedback, and
conversation turns, plus the Qdrant collection name and vector count.

For MongoDB Compass, connect with:

```text
mongodb://supplyguard:supplyguard@localhost:27017/supplyguard?authSource=admin
```

Inspect the `supplyguard` database and its `chunks`, `records`, `ingestion_runs`, `audit_events`,
`feedback`, and `conversation_turns` collections. For Qdrant, no additional desktop application is
needed: open its built-in dashboard, select `supplyguard_chunks_v1`, inspect point count and payload
schema, and use the Console tab for filtered searches.

Useful terminal checks:

```bash
docker volume ls | grep -E 'mongo_data|qdrant_data'
docker compose exec mongo mongosh \
  'mongodb://supplyguard:supplyguard@localhost:27017/supplyguard?authSource=admin' \
  --quiet --eval 'db.chunks.countDocuments(); db.records.countDocuments()'
curl -s http://localhost:6333/collections | python -m json.tool
curl -s http://localhost:6333/collections/supplyguard_chunks_v1 | python -m json.tool
```

### API status-code behavior

| Endpoint or condition | Status | Meaning |
|---|---:|---|
| `POST /v1/ask` valid request | 200 | A typed answer was produced, including safe refusal/degradation warnings |
| `POST /v1/feedback` valid request | 201 | Feedback was created or idempotently upserted |
| `GET /v1/storage/stats` | 200 / 503 | Counts available / persistence dependency unavailable |
| `GET /health/live` | 200 | API process is alive |
| `GET /health/ready` | 200 / 503 | Required dependencies ready / one or more degraded |
| Missing or invalid API key | 401 | Authentication failed |
| Invalid request schema | 422 | Pydantic validation failed |
| Unknown route | 404 | Endpoint does not exist |
| Unexpected server failure | 500 | Generic response; details remain in structured logs |

A weak-evidence refusal, an unavailable optional MCP result, or failed local generation still returns
HTTP 200 because the API successfully processed the request and returns a machine-readable answer,
zero/low confidence, warnings, and a failed tool trace. Transport status describes API execution;
the response fields describe AI/tool outcome. Storage inspection returns 503 when counts cannot be
trusted because its purpose is specifically dependency verification.

Example requests:

```text
What are the World Bank core procurement principles?
Which state has the most disaster declarations?
Use the FEMA tool to count declarations for CA in 2025.
What is the World Bank procurement director's home address?
```

### Run tests

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
ruff check --line-length 100 src tests scripts ui
```

## Limitations

1. PyMuPDF extracts text and tables, but image-only pages are only marked for OCR; the application does not yet run OCR or a vision model.
2. The lexical retriever is a compact term-frequency implementation, not a full BM25 index.
3. The local LLM router handles varied phrasing but can still misclassify domain-overlapping questions; the deterministic fallback is intentionally narrower.
4. Retrieval confidence is a ranking-derived heuristic and has not been statistically calibrated.
5. The local Mistral model may produce weaker synthesis than a larger hosted model, particularly for multi-page comparisons.
6. MongoDB API keys are intentionally simple demonstration credentials, not a production identity system.
7. Seeding performs a full CSV scan and batched upsert; incremental source-delta ingestion is not implemented.

## What I would improve with another day

I would first measure retrieval rather than immediately add more infrastructure. I would label relevant pages for the document questions, compare chunk sizes and tune top-k based on recall and citation precision. After that I would:

- add OCR with confidence-based routing for scanned pages;
- replace the lexical scorer with BM25;
- add a local cross-encoder reranker;
- batch MongoDB upserts for faster CSV ingestion;
- introduce effective-date-aware claim extraction for broader contradiction detection;
- add integration tests using temporary MongoDB and Qdrant containers;
- add a reviewed groundedness metric to the evaluation report;
- build and report an intent confusion matrix, then refine few-shot routing examples only for measured misclassifications.

I would not fine-tune first. The likely early failures in this application are retrieval, parsing and routing failures, and fine-tuning would not fix those.
