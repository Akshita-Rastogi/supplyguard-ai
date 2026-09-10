import re
from datetime import UTC, datetime
from uuid import uuid4

from supplyguard.core.config import Settings
from supplyguard.domain.models import AskRequest, AskResponse, Intent
from supplyguard.infrastructure.mcp_client import MCPToolError
from supplyguard.infrastructure.ollama import OllamaUnavailable
from supplyguard.infrastructure.vector import VectorStoreError
from supplyguard.retrieval.hybrid import retrieve
from supplyguard.services.analytics import answer_analytics
from supplyguard.services.contradictions import detect
from supplyguard.services.memory import build_context, is_follow_up, load_recent_turns, store_turn
from supplyguard.services.router import classify_with_llm

US_STATE_CODES = frozenset(
    [
        "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID",
        "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS",
        "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK",
        "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV",
        "WI", "WY", "DC", "PR", "VI", "GU", "MP", "AS",
    ]
)


def extract_state_code(text: str) -> str:
    """Extract a valid state/territory code without mistaking words such as 'to'."""
    for token in re.findall(r"\b[A-Z]{2}\b", text):
        if token in US_STATE_CODES:
            return token
    match = re.search(r"\b(?:for|state(?:\s+of)?)\s+([a-z]{2})\b", text, re.IGNORECASE)
    candidate = match.group(1).upper() if match else ""
    return candidate if candidate in US_STATE_CODES else ""


class Orchestrator:
    """Coordinate memory, routing, evidence, tools, generation, and auditing."""

    def __init__(self, db, vectors, ollama, mcp, settings: Settings):
        """Receive infrastructure dependencies explicitly for testing and replacement."""
        self.db, self.vectors, self.ollama, self.mcp, self.settings = db, vectors, ollama, mcp, settings

    async def ask(self, request: AskRequest, actor: str) -> AskResponse:
        """Execute one question safely and return an inspectable typed response."""
        request_id = str(uuid4())
        history = await load_recent_turns(
            self.db, request.tenant_id, request.conversation_id, self.settings.memory_max_turns
        )
        used_history = history if is_follow_up(request.question) else []
        # Only referential follow-ups inherit history; new topics remain independent.
        contextual_question = build_context(request.question, used_history,
                                            self.settings.memory_max_chars)
        intent, route_source = await classify_with_llm(contextual_question, self.ollama)
        citations, warnings = [], []
        trace = [{"component": "intent_router", "strategy": route_source,
                  "selected_intent": intent.value}]
        if request.conversation_id:
            trace.append({"component": "session_memory", "turns_used": len(used_history),
                          "max_turns": self.settings.memory_max_turns})
        if intent == Intent.UNSUPPORTED:
            answer = ("I don't know based on the available evidence. This question is outside "
                      "the supported World Bank, NIST, FEMA analytics, and FEMA MCP domains.")
            confidence = 0.0
            warnings.append("No retrieval, database aggregation, or external tool was executed.")
            trace.append({"component": "scope_guard", "status": "refused"})
        elif intent == Intent.ANALYTICS:
            # Arithmetic stays in MongoDB rather than relying on LLM calculations.
            answer, analytics_trace = await answer_analytics(
                self.db, request.tenant_id, contextual_question
            )
            trace.extend(analytics_trace)
            confidence = 0.9 if analytics_trace and analytics_trace[0]["rows"] else 0.1
        elif intent == Intent.LIVE_RISK:
            # Current-turn arguments win; memory only fills values omitted by a follow-up.
            state = extract_state_code(request.question)
            year_match = re.search(r"\b(19|20)\d{2}\b", request.question)
            if used_history and not state:
                state = extract_state_code(contextual_question)
            if used_history and not year_match:
                year_match = re.search(r"\b(19|20)\d{2}\b", contextual_question)
            arguments = {"state": state,
                         "year": int(year_match.group()) if year_match else 0}
            try:
                result = await self.mcp.call("disaster_statistics", arguments)
                answer = (f"The local MCP tool computed {result['total']} declarations. "
                          f"Incident breakdown: {result['by_incident_type'][:8]}.")
                trace.append({"tool": "mcp.disaster_statistics", "arguments": arguments,
                              "source": result["source"], "result_count": result["total"]})
                confidence = 0.95
                warnings.append("Result comes from a local FEMA snapshot; inspect its refresh timestamp.")
            except MCPToolError:
                answer = "The disaster-data MCP tool is unavailable; no risk result was fabricated."
                trace.append({"tool": "mcp.disaster_statistics", "arguments": arguments,
                              "status": "failed"})
                confidence = 0.0
                warnings.append("MCP dependency failure.")
        else:
            # Document answers require retrieved evidence and pass through refusal checks.
            try:
                citations = await retrieve(self.db, self.vectors, self.ollama, request.tenant_id,
                                           contextual_question, request.filters)
            except (OllamaUnavailable, VectorStoreError):
                citations = []
                warnings.append("The local embedding or vector service is unavailable; retrieval was safely refused.")
            trace.append({"tool": "qdrant_dense_plus_lexical_rrf", "candidates": len(citations),
                          "embedding_model": self.settings.ollama_embed_model})
            confidence = sum(c.score for c in citations[:3]) / max(1, min(3, len(citations)))
            warnings.extend(detect(citations))
            if not citations or confidence < self.settings.min_evidence_score:
                answer = "I don't know based on the available evidence. Add a relevant source or narrow the question."
                warnings.append("Response refused because evidence was below the configured threshold.")
            else:
                evidence = "\n\n".join(
                    f"[S{i}] {c.title} ({c.locator})\n{c.excerpt}"
                    for i, c in enumerate(citations, 1)
                )[:self.settings.max_context_chars]
                try:
                    answer = await self.ollama.generate(contextual_question, evidence)
                    trace.append({"tool": "ollama_generate", "model": self.settings.ollama_chat_model})
                except OllamaUnavailable:
                    answer = "Local generation is temporarily unavailable. Retrieved evidence is returned in citations."
                    warnings.append("Ollama generation failed; no ungrounded fallback was used.")
        response = AskResponse(request_id=request_id, answer=answer, intent=intent,
            confidence=round(confidence, 3), citations=citations, tool_trace=trace, warnings=warnings)
        await self.db.audit_events.insert_one({"request_id": request_id, "tenant_id": request.tenant_id,
            "actor": actor, "question": request.question, "conversation_id": request.conversation_id,
            "memory_turns_used": len(used_history), "intent": intent.value,
            "response": response.model_dump(mode="json"), "created_at": datetime.now(UTC)})
        await store_turn(self.db, request.tenant_id, request.conversation_id, request_id,
                         request.question, answer)
        return response
