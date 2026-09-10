"""Deterministic answer-quality metrics shared by evaluation scripts and tests."""
import re


def important_words(text: str) -> set[str]:
    """Extract meaningful tokens for transparent lexical quality proxies."""
    stop = {"the", "and", "from", "with", "should", "expected", "computed", "plus"}
    return {word for word in re.findall(r"[a-z0-9]+", text.lower())
            if len(word) > 3 and word not in stop}


def answer_metrics(case: dict, result: dict) -> dict[str, float]:
    """Calculate completeness, grounding, citation, and refusal proxies."""
    answer = result["answer"]
    expected = important_words(case["expected"])
    answer_words = important_words(answer)
    evidence_words = important_words(" ".join(c["excerpt"] for c in result["citations"]))
    completeness = len(expected & answer_words) / max(1, len(expected))
    factual_words = answer_words - {"based", "available", "evidence", "source", "know"}
    groundedness = len(factual_words & evidence_words) / max(1, len(factual_words))
    labels = set(re.findall(r"\[S(\d+)\]", answer))
    citation_coverage = min(len(labels) / max(1, len(result["citations"])), 1.0)
    refused = "don't know" in answer.lower() or "cannot" in answer.lower()
    expected_refusal = case["category"] in {
        "refusal", "unsupported", "adversarial", "tenant_isolation"
    }
    return {"completeness": completeness, "groundedness": groundedness,
            "citation_coverage": citation_coverage,
            "refusal_correctness": float(refused == expected_refusal)}
