import pytest

from supplyguard.domain.models import AskRequest, Citation, Intent
from supplyguard.retrieval.hybrid import lexical_score
from supplyguard.services.contradictions import detect
from supplyguard.services.orchestrator import extract_state_code
from supplyguard.services.router import classify, classify_with_llm


def test_router_distinguishes_computation_from_policy():
    assert classify("Which state has the most disaster declarations?") == Intent.ANALYTICS
    assert classify("Who approves purchases above the threshold?") == Intent.DOCUMENT
    assert classify("Use the FEMA tool for CA in 2025") == Intent.LIVE_RISK
    assert classify("Who is Akshita Rastogi?") == Intent.UNSUPPORTED
    assert classify("What is the capital of France?") == Intent.UNSUPPORTED
    assert classify("What is today's weather?") == Intent.UNSUPPORTED


@pytest.mark.asyncio
async def test_hybrid_router_uses_llm_for_non_explicit_question():
    class Ollama:
        async def classify_intent(self, question):
            return Intent.ANALYTICS

    assert await classify_with_llm("Compare declaration totals", Ollama()) == (
        Intent.ANALYTICS, "ollama")


@pytest.mark.asyncio
async def test_hybrid_router_protects_explicit_mcp_command():
    class Ollama:
        async def classify_intent(self, question):
            raise AssertionError("explicit tool request must not call the model")

    assert await classify_with_llm("Use the FEMA tool for CA", Ollama()) == (
        Intent.LIVE_RISK, "explicit_rule")


@pytest.mark.asyncio
async def test_hybrid_router_corrects_impossible_procurement_analytics_route():
    class Ollama:
        async def classify_intent(self, question):
            return Intent.ANALYTICS

    assert await classify_with_llm("Which procurement method fits complex risk?", Ollama()) == (
        Intent.DOCUMENT, "ollama_guardrail")


@pytest.mark.asyncio
async def test_identity_question_is_refused_before_llm_or_database_access():
    class Ollama:
        async def classify_intent(self, question):
            raise AssertionError("clear identity request must not call the model")

    assert await classify_with_llm("Who is Akshita Rastogi?", Ollama()) == (
        Intent.UNSUPPORTED, "explicit_rule")


def test_lexical_score_handles_empty_and_relevance():
    assert lexical_score("", "anything") == 0
    assert lexical_score("shipment escalation", "shipment escalation policy") > lexical_score(
        "shipment escalation", "annual leave")


def test_contradiction_detector_surfaces_version_conflict():
    evidence = [Citation(source_id="a", title="v1", locator="1", excerpt="Approval is USD 10,000", score=.8),
                Citation(source_id="b", title="v2", locator="1", excerpt="Approval is USD 7,500", score=.9)]
    assert "Potential contradiction" in detect(evidence)[0]


def test_request_normalizes_whitespace_and_rejects_bad_tenant():
    assert AskRequest(question="  top   states ", tenant_id="demo-corp").question == "top states"
    with pytest.raises(ValueError):
        AskRequest(question="hello", tenant_id="../escape")


def test_state_extraction_does_not_read_to_from_tool():
    assert extract_state_code("Use the FEMA tool to count CA declarations") == "CA"
    assert extract_state_code("Use the FEMA tool to count declarations") == ""
    assert extract_state_code("Use the FEMA tool for ca in 2025") == "CA"
