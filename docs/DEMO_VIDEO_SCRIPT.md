# SupplyGuard AI: 5–7 minute demonstration

## Before recording

Do not run ingestion during the video. Start with the already seeded persistent volumes.

```bash
cd "/Users/akshitarastogi/Documents/Codex/2026-09-09/si/outputs/supplyguard-ai"
docker compose up -d --build
docker compose ps
curl -s http://localhost:8000/health/ready | python -m json.tool
curl -s http://localhost:8000/v1/storage/stats \
  -H 'X-API-Key: demo-key' | python -m json.tool
```

Before the recording, run the evaluation once so its CSV contains results from the current code:

```bash
docker compose exec api python scripts/evaluate.py
```

Prepare these windows in this order:

1. Streamlit: `http://localhost:8501`
2. FastAPI documentation: `http://localhost:8000/docs`
3. Qdrant: `http://localhost:6333/dashboard`
4. MongoDB Compass, connected to
   `mongodb://supplyguard:supplyguard@localhost:27017/supplyguard?authSource=admin`
5. VS Code opened at the repository root
6. A terminal opened at the repository root

Increase the browser and terminal font enough for the recording. Collapse bookmarks, close personal
tabs, hide `.env`, and turn on Do Not Disturb.

## Record on macOS

1. Press `Command + Shift + 5`.
2. Select **Record Entire Screen**, or **Record Selected Portion** if personal windows are visible.
3. Open **Options** and select the intended microphone. Choose a save location with enough space.
4. Turn off notifications using Control Center and enable Do Not Disturb.
5. Click **Record**. Pause for two seconds before speaking.
6. Press `Command + Control + Escape` or click the stop icon in the menu bar when finished.

Prefer a single continuous take. Move the pointer slowly, avoid rapid scrolling, and allow every
answer to finish before speaking about it.

## Screen and narration plan

### 0:00–0:35 — Streamlit home and objective

**Screen:** Streamlit hero and sidebar. Click **New chat** before starting.

**Say:**

“This is SupplyGuard AI, my local implementation of the AI Engineer assessment. It answers from
documents, computes answers from structured data, invokes an external MCP tool, refuses unsupported
questions, and captures feedback. I kept the required solution lightweight, but added
production-aware boundaries where they demonstrate engineering judgment. All generation and
embeddings remain local through Ollama; there is no paid or cloud model dependency.”

“The corpus is intentionally more difficult than the minimum: three official World Bank and NIST
PDFs totaling 603 pages, including tables, figures, acronyms and blank or image-only pages, plus
70,402 official OpenFEMA rows.”

### 0:35–1:05 — Terminal: deployment and persistence

**Screen:** Terminal. Run:

```bash
docker compose ps
curl -s http://localhost:8000/health/ready | python -m json.tool
curl -s http://localhost:8000/v1/storage/stats \
  -H 'X-API-Key: demo-key' | python -m json.tool
```

**Say:**

“Docker Compose runs five local services: FastAPI, Streamlit, MongoDB, Qdrant and a failure-isolated
MCP server. Readiness checks MongoDB, Qdrant, Ollama and MCP independently. The storage
endpoint proves that ingestion completed: MongoDB contains 2,198 canonical chunks and 70,402
structured records, while Qdrant contains 2,198 matching vectors. Named Docker volumes preserve
both databases across ordinary restarts.”

“Ingestion is idempotent. Stable source and vector IDs turn reruns into upserts rather than
duplicates, and an ingestion-run record captures parser failures.”

### 1:05–2:05 — Document RAG with citations

**Screen:** Streamlit **Ask** tab. Enter:

```text
What are the World Bank core procurement principles?
```

Open **Evidence and citations** and **Tool execution trace**.

**Say while it runs:**

“The loading modal covers local intent classification, retrieval and generation. The router uses
Mistral with a typed four-value JSON schema, plus deterministic safety guardrails and an outage
fallback. It does not use fuzzy matching.”

**Say after the answer:**

“This took the document route. The query was embedded with `nomic-embed-text`, which produces
768-dimensional vectors. Qdrant retrieves semantic candidates, MongoDB supplies lexical candidates,
and reciprocal-rank fusion combines the two ranks without pretending their raw scores are directly
comparable. The final six chunks are passed to Mistral as an evidence-only prompt.”

“Citations are not merely text invented by the model. The API independently returns the source
title, page locator, excerpt and retrieval score for the actual retrieved chunks.”

### 2:05–2:45 — Structured-data computation

**Screen:** Ask:

```text
Which state has the most disaster declarations?
```

Open the tool trace.

**Say:**

“This answer comes from a server-owned MongoDB aggregation, not LLM arithmetic. It returns
California with 397 distinct disaster numbers. The distinction matters: OpenFEMA repeats one
disaster across designated-area rows, so simply counting CSV rows would incorrectly return Texas
with 5,444 rows. I explicitly group by state and disaster number first, then count unique
declarations. User text cannot inject arbitrary Mongo operators because grouping fields and the
pipeline are allowlisted in code.”

### 2:45–3:35 — External MCP tool and visible tool output

**Screen:** Ask:

```text
Use the FEMA tool to count declarations for CA in 2025
```

Open **Tool execution trace**.

**Say:**

“The explicit tool instruction selects the MCP route. FastAPI acts as an MCP client and calls the
separate Streamable HTTP MCP server. The server validates the state and year, reads the local FEMA
snapshot, and returns eight declarations, all Fire. The trace exposes the selected tool, arguments,
source and result count, satisfying the requirement to show the tool output used in the response.”

“If MCP is unavailable, the assistant returns a failed-tool trace and does not fabricate a result.”

### 3:35–4:10 — Multi-turn memory

**Screen:** Without clicking **New chat**, ask:

```text
What about 2024?
```

Open the trace and point to `session_memory`.

**Say:**

“This incomplete follow-up reuses California from the previous turn and applies the new year. The
UI appends every result instead of overwriting earlier turns, and each turn has independent
feedback.”

“Memory is bounded and tenant-isolated. MongoDB loads at most six turns for this conversation, the
context is capped at 4,000 characters, and a 24-hour TTL removes abandoned sessions. Conversation
history resolves references, but never becomes factual evidence; document answers still require
retrieval.”

### 4:10–4:40 — Reliability, refusal and feedback

**Screen:** Click **New chat**, then ask:

```text
What is the World Bank procurement director's home address?
```

Submit **Helpful** or **Not helpful** feedback on one response.

**Say:**

“A normalized retrieval threshold of 0.35 gates document generation. If evidence is missing or weak,
the system says it does not know instead of using Mistral’s background knowledge. Retrieved text is
also labelled untrusted so document prompt injection is not treated as an instruction.”

“Feedback is upserted in MongoDB against the request ID. Once stored, that turn disables duplicate
submission. This is not reinforcement learning or RLHF: no model weights, reward model or policy are
updated. It is an offline quality signal that can be reviewed and converted into regression cases.”

### 4:40–5:20 — MongoDB Compass and Qdrant

**Screen:** MongoDB Compass. Open `supplyguard`, then briefly show:

- `chunks`
- `records`
- `audit_events`
- `feedback`
- `conversation_turns`
- `ingestion_runs`

**Say:**

“MongoDB owns canonical text, typed structured data and operational state. The audit ledger records
the question, route, confidence, citations, warnings and tool trace, so a bad result can be traced to
routing, retrieval, generation or tool execution. Feedback and bounded conversation turns are also
persistent.”

**Screen:** Qdrant dashboard. Open `supplyguard_chunks_v1` and show the 2,198 points and payload.

**Say:**

“Qdrant owns vector retrieval. I chose it over FAISS because persistence, service access and
metadata filtering are built in, and over local MongoDB Community vector search because that would
pretend an Atlas capability exists locally. Every search applies a tenant payload filter.”

### 5:20–6:15 — VS Code: explain the code flow

**Screen:** VS Code Explorer, then use `Command + P` to open these files briefly:

1. `src/supplyguard/services/orchestrator.py`
2. `src/supplyguard/retrieval/hybrid.py`
3. `src/supplyguard/services/analytics.py`
4. `src/supplyguard/mcp_server.py`
5. `src/supplyguard/services/memory.py`

**Say:**

“The request starts in `main.py`, where lifespan creates shared async clients. `routes.py` performs
API-key authentication and Pydantic validation. `Orchestrator.ask` is the explicit control plane:
it loads bounded memory, routes the question, executes RAG, Mongo aggregation or MCP, builds the typed
response, writes the audit event, and stores the conversation turn.”

“`hybrid.retrieve` performs tenant-filtered dense and lexical retrieval and RRF. `analytics.py`
constructs safe aggregation pipelines. `mcp_server.py` owns tool schemas and source computation.
`memory.py` detects referential follow-ups, bounds context and degrades safely if memory storage is
unavailable.”

“I deliberately avoided LangChain or LangGraph because three explicit routes are clearer to test
and explain. A workflow graph would be justified later for resumable steps, parallel tools or human
approval.”

### 6:15–6:50 — Chunking, evaluation and close

**Screen:** Streamlit **Evaluation** tab or `chunking_benchmark.csv`, then README evaluation section.

**Say:**

“Chunking was selected through measurement rather than convention. I compared 160/30, 240/40 and
400/60. The selected 160 words with 30 overlap produced 2,198 chunks, 74.6 percent concept recall at
six, 100 percent hit rate, and the smallest evidence packet. Tables are separated from narrative,
and chunks never cross page elements. The larger 400-word option had better first-hit rank but used
91 percent more context, so I chose the better precision-context trade-off.”

“The golden set contains the required four document, two structured, one tool and one refusal case,
plus six harder cases. The evaluator records actual answers, completeness, groundedness, citation
coverage, refusal correctness and pass or fail. These are transparent deterministic proxies, not a
claim of perfect production accuracy.”

“The extra engineering features are hybrid retrieval, public mixed-content ingestion, bounded
session memory, replayable audit records, tenant isolation, prompt-injection boundaries,
contradiction warnings, structured logging, correlation IDs, Prometheus metrics, readiness checks
and idempotent persistence. The result remains a lightweight assessment solution, but its failure
modes are explicit and observable.”

## If time is closer to five minutes

Shorten the video by:

- showing the refusal question without waiting for a second long document generation;
- showing only one MongoDB document and the Qdrant collection count;
- opening only `orchestrator.py` and `hybrid.py` in VS Code;
- summarizing evaluation in one sentence.

Do not skip the document answer, MongoDB computation, MCP trace, memory follow-up, refusal, feedback,
or persistent storage proof. Those screens collectively cover the full rubric.

## Short answers for likely reviewer questions

**Why fixed-size overlap instead of fully structure-aware chunking?**  
The parser is structure-aware at the page-element level: tables and text are separated and chunks do
not cross pages. Within an element, fixed word windows are deterministic, easy to reproduce, and
worked best in the measured corpus. A heading-aware semantic splitter is a next experiment, not an
assumed improvement.

**Why MongoDB and Qdrant?**  
MongoDB fits flexible source metadata, structured FEMA rows, audit, feedback and memory. Qdrant
provides persistent local vector search and payload filtering. This avoids forcing two different
data responsibilities into one weak abstraction.

**Why Mistral and Nomic?**  
Mistral is an instruction-tuned local model already available on the laptop and is practical for a
small evidence-only generator. Nomic is a dedicated 768-dimensional retrieval model and is faster
and more appropriate for similarity search than reusing a generation model.

**Why is confidence not answer accuracy?**  
It is derived from retrieval ranks and measures evidence strength. It is not statistically
calibrated against factual correctness, so the UI labels it evidence confidence.

**What are the main limitations?**  
There is no OCR or vision extraction for image-only pages, lexical search is not full BM25, the local
model can still synthesize imperfectly, retrieval confidence is heuristic, and demo API keys are not
enterprise identity management.

**What would you do with another day?**  
Label relevant pages, tune retrieval against recall and citation precision, add OCR, test BM25 and a
local reranker, expand integration tests, and build an intent confusion matrix before considering
fine-tuning.
