from supplyguard.domain.models import Intent
from supplyguard.infrastructure.ollama import OllamaUnavailable

DOCUMENT_DOMAINS = ("procurement", "purchase", "tender", "bid", "borrower", "contract",
                    "vendor", "nist", "supplier", "world bank", "supply-chain",
                    "supply chain", "cybersecurity", "risk management", "due diligence",
                    "c-scrm", "ppsd")
ANALYTICS_DOMAINS = ("fema", "disaster", "declaration", "incident type",
                     "structured data", "csv", "openfema")
ANALYTICS_OPERATIONS = ("highest", "most", "total", "top ", "how many", "count",
                        "rank", "breakdown", "show")
SENSITIVE_OR_EXTERNAL = ("home address", "phone number", "email address", "api key",
                         "password", "secret", "today's weather", "current weather",
                         "stock price", "exchange rate", "another tenant", "tenant-b")


def analytics_eligible(question: str) -> bool:
    """Require both a FEMA subject and supported computation before database access."""
    q = question.lower()
    return (any(term in q for term in ANALYTICS_DOMAINS)
            and any(term in q for term in ANALYTICS_OPERATIONS))


def clearly_unsupported(question: str) -> bool:
    """Reject obvious personal, secret, cross-tenant, and unrelated live-data requests."""
    q = question.lower().strip()
    if any(term in q for term in SENSITIVE_OR_EXTERNAL):
        return True
    identity_request = q.startswith(("who is ", "tell me about ", "identify "))
    return identity_request and not any(term in q for term in DOCUMENT_DOMAINS)


def in_scope_subject(question: str) -> bool:
    """Return whether text names either of the application's evidence domains."""
    q = question.lower()
    return any(term in q for term in (*DOCUMENT_DOMAINS, *ANALYTICS_DOMAINS))


def explicit_classify(question: str) -> Intent | None:
    """Protect explicit tool commands from probabilistic LLM misrouting."""
    q = question.lower()
    if clearly_unsupported(q):
        return Intent.UNSUPPORTED
    if any(marker in q for marker in ("use the fema tool", "use fema tool", "mcp tool",
                                      "live disaster risk")):
        return Intent.LIVE_RISK
    if not in_scope_subject(q):
        return Intent.UNSUPPORTED
    return None


def classify(question: str) -> Intent:
    """Provide a deterministic fallback when local LLM classification is unavailable."""
    q = question.lower()
    explicit = explicit_classify(question)
    if explicit is not None:
        return explicit
    if any(x in q for x in ("live disaster risk", "mcp", "fema tool")):
        return Intent.LIVE_RISK
    if analytics_eligible(q):
        return Intent.ANALYTICS
    if any(term in q for term in DOCUMENT_DOMAINS):
        return Intent.DOCUMENT
    return Intent.UNSUPPORTED


async def classify_with_llm(question: str, ollama) -> tuple[Intent, str]:
    """Use guarded local-LLM routing, falling back safely to deterministic rules."""
    explicit = explicit_classify(question)
    if explicit is not None:
        return explicit, "explicit_rule"
    try:
        predicted = await ollama.classify_intent(question)
        q = question.lower()
        # LLM output proposes a route; deterministic eligibility decides whether
        # that route may access a database or tool.
        if predicted == Intent.ANALYTICS and not analytics_eligible(q):
            corrected = (
                Intent.DOCUMENT
                if any(term in q for term in DOCUMENT_DOMAINS)
                else Intent.UNSUPPORTED
            )
            return corrected, "ollama_guardrail"
        if predicted == Intent.LIVE_RISK:
            if analytics_eligible(q):
                return Intent.ANALYTICS, "ollama_guardrail"
            corrected = (
                Intent.DOCUMENT
                if any(term in q for term in DOCUMENT_DOMAINS)
                else Intent.UNSUPPORTED
            )
            return corrected, "ollama_guardrail"
        if predicted == Intent.UNSUPPORTED and analytics_eligible(q):
            return Intent.ANALYTICS, "ollama_guardrail"
        if predicted == Intent.UNSUPPORTED and any(term in q for term in DOCUMENT_DOMAINS):
            return Intent.DOCUMENT, "ollama_guardrail"
        if predicted == Intent.DOCUMENT and analytics_eligible(q):
            return Intent.ANALYTICS, "ollama_guardrail"
        return predicted, "ollama"
    except OllamaUnavailable:
        return classify(question), "rule_fallback"
