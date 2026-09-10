from supplyguard.services.memory import build_context, is_follow_up


def test_memory_context_supports_follow_up_questions():
    turns = [{"question": "Use the FEMA tool for CA in 2025",
              "answer": "There were eight declarations."}]
    context = build_context("What about 2024?", turns, max_chars=1000)
    assert "CA in 2025" in context
    assert context.endswith("What about 2024?")


def test_memory_context_is_bounded_and_keeps_current_question():
    turns = [{"question": "x" * 500, "answer": "y" * 500}]
    context = build_context("Current follow-up", turns, max_chars=120)
    assert context.startswith("[Older conversation truncated]")
    assert context.endswith("Current follow-up")


def test_no_history_does_not_rewrite_question():
    assert build_context("Standalone question", [], max_chars=100) == "Standalone question"


def test_only_ambiguous_follow_ups_reuse_memory():
    assert is_follow_up("What about 2024?")
    assert is_follow_up("And which incident type was most common?")
    assert not is_follow_up("What does NIST recommend for supplier assessments?")
