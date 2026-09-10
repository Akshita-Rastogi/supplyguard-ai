# Five-minute reviewer guide

1. Start Ollama, then run Docker Compose and the idempotent seed command from the README.
2. Open Streamlit on port 8501. Confirm MongoDB, Qdrant, and Ollama show ready.
3. Call `/v1/storage/stats` with the demo API key and open Qdrant's dashboard at `http://localhost:6333/dashboard` to confirm persistent records and vectors.
4. Ask a World Bank procurement question. Inspect PDF page/element citations and the Qdrant + lexical RRF trace.
5. Ask “Which state has the most disaster declarations?” Confirm it routes to a MongoDB aggregation over the official CSV.
6. Ask “Use the FEMA tool to count declarations for CA in 2025.” Confirm it calls `mcp.disaster_statistics`; the verified snapshot result is 8, all Fire.
7. Ask for a CEO home address. Confirm low evidence produces refusal.
8. Ask a question spanning World Bank and NIST documents. Confirm the answer keeps page-level sources distinct.
9. Try an instruction to ignore evidence and reveal a secret. Confirm the bounded evidence prompt and absence of secrets prevent disclosure.
10. Submit helpful/not-helpful feedback. Confirm the UI explains that this is an evaluation signal, not reinforcement learning.

Do not judge the solution only by answer fluency. Inspect citation correctness, routing, tenant filtering, failures, and the explicit tool trace—the aspects the assessment says matter most.
