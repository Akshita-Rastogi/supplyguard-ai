# Assessment-to-implementation map

This file separates the assessment instructions from optional production extensions.

| Assessment requirement | Concrete implementation | How to demonstrate |
|---|---|---|
| Ask document questions | `/v1/ask` document route | Ask about procurement approach or contract management |
| Retrieve relevant content | Ollama embeddings + Qdrant dense search + Mongo lexical search + RRF | Expand citations in Streamlit |
| Grounded answers | Bounded evidence-only Ollama prompt | Inspect answer and `[S#]` citations |
| Source citations | Title, PDF page/element/chunk locator, excerpt, score | Evidence panel |
| Refuse unsupported questions | Minimum evidence threshold and safe dependency fallbacks | Ask for a private/home address |
| Structured CSV questions | Server-built, allowlisted Mongo aggregation over OpenFEMA | Ask top states or incident types by declarations |
| Answers from computation | Aggregation result, never prompt arithmetic | Inspect tool trace |
| One external tool / MCP preferred | Real MCPServer Streamable HTTP service over full FEMA CSV | Ask disaster totals for CA in 2025 |
| Assistant chooses tool | Guarded local-LLM classifier with explicit-tool rule and deterministic fallback | Compare document/data/risk questions and inspect routing trace |
| Show tool output used | Typed `tool_trace` in API and UI | Expand tool execution trace |
| Reliability mechanism | RRF score threshold, refusal and prompt-injection boundary | Run the refusal case |
| Feedback loop | Idempotent helpful/not-helpful endpoint and UI | Submit feedback after an answer |
| Explain whether RL | README explicitly states it is evaluation data, not RL | Feedback section |
| Eight evaluation questions | Golden set begins with the required 4 document, 2 structured, 1 tool and 1 refusal cases | Evaluation tab and JSON |
| README architecture/chunking/retrieval/tools/failures/limitations | Detailed human-written README | README sections |
| Source, sample documents, sample CSV | Repository contains code, three official PDFs and full official CSV | Corpus tab |

## Intentional extensions

Streamlit, MongoDB/Qdrant separation, local Ollama, bounded session memory, measured chunk benchmarking, answer-quality metrics, correlation logging, Prometheus, health probes, MCP isolation, audit ledger, contradiction detection, public-data provenance and ingestion run records are extensions requested by the candidate. They are not misrepresented as mandatory assessment requirements.
