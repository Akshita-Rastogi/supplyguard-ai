# SupplyGuard AI — 6-minute demo speech

Text in brackets is a screen cue. Do not read it aloud.

## 0:00–0:45 — Introduction and runtime

[Show Streamlit home, Corpus, then Terminal with `docker compose ps` and storage stats.]

Hello, I am Akshita, and this is SupplyGuard AI. It covers document RAG, structured-data computation,
MCP tool calling, uncertainty, feedback and evaluation. I intentionally used difficult official data:
three World Bank and NIST PDFs totalling 603 pages, including tables and figures, plus 70,402 OpenFEMA
rows.

Everything runs locally. Ollama serves Mistral for routing and generation and `nomic-embed-text` for
768-dimensional embeddings. Docker Compose runs FastAPI, Streamlit, MongoDB, Qdrant and a separate
MCP server. Ingestion uses stable IDs and upserts, so rerunning it does not create duplicates.

## 0:45–1:45 — Document RAG and chunking

[Ask: “What are the World Bank core procurement principles?” Open citations and trace.]

The router selects document RAG. Qdrant returns 20 semantic candidates and MongoDB returns 20 lexical
candidates. Reciprocal-rank fusion combines them, and the best six chunks become the evidence. Mistral
must answer only from that evidence, while citations expose the source, page, element, excerpt and score.

I measured three chunk settings. The selected 160 words with 30 overlap achieved 74.6 percent recall at
six, 100 percent hit rate, 0.413 MRR and only 749 context words. The 240/40 setting achieved 70.5 percent
recall. The 400/60 setting gave similar recall but required 1,434 context words. Therefore, 160/30 gave
the best balance of recall, precision and local-model context. Tables remain separate, and chunks never
cross page elements.

## 1:45–2:30 — Structured computation

[Ask: “Which state has the most disaster declarations?”]

MongoDB computes California with 397 distinct disaster numbers; the LLM performs no arithmetic.
OpenFEMA repeats one disaster across designated areas, so counting raw rows incorrectly produces Texas
with 5,444. The pipeline first deduplicates state and disaster number. Fields and aggregation operations
are allowlisted, preventing users from injecting database operators.

## 2:30–3:20 — MCP and memory

[Ask: “Use the FEMA tool to count declarations for CA in 2025.” Open its trace. Then ask: “What about
2024?”]

This request selects the independent Streamable HTTP MCP service. It validates its arguments and returns
eight declarations in 2025, all Fire. The UI shows the exact tool arguments, source and result. If the
tool fails, the assistant reports that failure instead of inventing an answer.

The follow-up reuses California and changes the year. Memory is isolated by tenant and conversation,
bounded to six turns and 4,000 characters, and expires after 24 hours. It helps resolve references but
never replaces evidence.

## 3:20–4:05 — Reliability and feedback

[Start a new chat. Ask: “Who is Akshita Rastogi?” Then submit feedback on a result.]

The router supports document, analytics, MCP and unsupported outcomes. The LLM proposes an intent, but
deterministic scope checks stop unrelated questions before retrieval, database access or tool execution.
Unsupported requests have zero confidence, and document answers are refused below the 0.35 retrieval
threshold.

Feedback is saved in MongoDB by request ID, and the UI disables duplicate submissions. This is not RLHF:
it does not update model weights or behaviour online. It becomes reviewed data for later regression tests.

## 4:05–4:55 — Persistence and code

[Show MongoDB Compass collections, Qdrant collection and a vector payload; then open `orchestrator.py`,
`hybrid.py`, `analytics.py` and `mcp_server.py` in VS Code.]

MongoDB stores source chunks, FEMA records, feedback, conversations, audits and ingestion runs. Qdrant
stores embeddings and tenant-filtered metadata. I chose Qdrant for persistent local vector search and
filtering, rather than claiming MongoDB Community provides Atlas Vector Search.

`Orchestrator.ask` connects memory, routing, RAG, analytics, MCP, refusal and audit logging.
`hybrid.py` implements rank fusion, `analytics.py` performs safe computation, and `mcp_server.py` validates
tool calls. The execution paths remain explicit and easy to explain.

## 4:55–6:00 — Evaluation and closing

[Show Evaluation tab and results CSV.]

The suite contains the required four document, two structured, one tool and one refusal case, plus six
difficult regression cases. It reports expected output, actual output and pass or fail. It measures answer
completeness, groundedness, citation coverage and refusal correctness, with a 0.50 passing threshold for
completeness and groundedness.

Beyond the assignment, I added hybrid retrieval, measured chunk selection, schema-constrained LLM routing,
deterministic scope guards, correct FEMA aggregation grain, bounded memory, an independent MCP service,
prompt-injection protection, replayable audits, structured logs, request IDs, metrics, health checks and
idempotent ingestion.

I describe this as production-aware, not fully production-ready. Current limitations are no OCR, a simple
lexical scorer, uncalibrated confidence and demo credentials. With another day, I would add OCR, BM25, a
local reranker, labelled retrieval evaluation and more integration tests.

This completes a fully local, evidence-grounded and explainable solution.
