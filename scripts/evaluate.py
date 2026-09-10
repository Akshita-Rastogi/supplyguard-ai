"""Run the golden set and write an honest, reviewable report; never invent actual results."""
import csv
import json
import os
from pathlib import Path

import httpx

from supplyguard.evaluation import answer_metrics

ROOT = Path(__file__).resolve().parents[1]
API = os.getenv("API_BASE_URL", "http://localhost:8000")
KEY = os.getenv("API_KEY", "demo-key")
EVALUATION_PATH = Path(os.getenv("EVALUATION_PATH", ROOT / "evaluation.json"))
RESULTS_PATH = Path(
    os.getenv("EVALUATION_RESULTS_PATH", ROOT / "output/evaluation/evaluation_results.csv")
)


def main():
    """Run every golden case against the API and write measured—not invented—results."""
    # Paths are configurable so the same script works both locally and in the
    # read-only API container, where only the evaluation output mount is writable.
    cases = json.loads(EVALUATION_PATH.read_text(encoding="utf-8"))
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with RESULTS_PATH.open("w", newline="", encoding="utf-8") as handle:
        fields = ["Category", "Question", "Expected", "Actual", "Completeness",
                  "Groundedness", "Citation Coverage", "Refusal Correctness", "Pass/Fail"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for case in cases:
            try:
                response = httpx.post(f"{API}/v1/ask", headers={"x-api-key": KEY},
                    json={"tenant_id": "demo-corp", "question": case["question"]}, timeout=120)
                response.raise_for_status()
                result = response.json()
                actual = result["answer"]
                scores = answer_metrics(case, result)
                # Document answers must be complete and grounded; other routes prioritize
                # task completion and correct refusal because they may not return citations.
                if case["category"] in {"document", "cross_document", "table", "acronym"}:
                    passed = scores["completeness"] >= 0.5 and scores["groundedness"] >= 0.5
                else:
                    passed = scores["completeness"] >= 0.5 and scores["refusal_correctness"] == 1
                status = "PASS" if passed else "FAIL"
            except httpx.HTTPError as exc:
                actual, status = f"ERROR: {type(exc).__name__}", "FAIL"
                scores = {name: 0.0 for name in ("completeness", "groundedness",
                          "citation_coverage", "refusal_correctness")}
            writer.writerow({"Category": case["category"], "Question": case["question"],
                             "Expected": case["expected"], "Actual": actual,
                             "Completeness": f"{scores['completeness']:.2f}",
                             "Groundedness": f"{scores['groundedness']:.2f}",
                             "Citation Coverage": f"{scores['citation_coverage']:.2f}",
                             "Refusal Correctness": f"{scores['refusal_correctness']:.2f}",
                             "Pass/Fail": status})
    print(f"Wrote {len(cases)} measured rows to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
