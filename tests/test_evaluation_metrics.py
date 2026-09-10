from supplyguard.evaluation import answer_metrics


def test_answer_metrics_measure_supported_complete_answer():
    case = {"category": "document", "expected": "supplier evaluation monitoring controls"}
    result = {"answer": "Supplier evaluation requires monitoring controls [S1].",
              "citations": [{"excerpt": "Supplier evaluation and monitoring controls are required."}]}
    scores = answer_metrics(case, result)
    assert scores["completeness"] == 1
    # The intentionally transparent lexical proxy does not stem requires/required.
    assert scores["groundedness"] >= 0.8
    assert scores["citation_coverage"] == 1


def test_refusal_metric_recognizes_expected_refusal():
    case = {"category": "refusal", "expected": "refuse unsupported evidence"}
    result = {"answer": "I don't know based on the available evidence.", "citations": []}
    assert answer_metrics(case, result)["refusal_correctness"] == 1
