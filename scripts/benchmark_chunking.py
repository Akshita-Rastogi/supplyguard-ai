"""Compare candidate chunk sizes with a reproducible retrieval-quality proxy."""
import csv
import json
import time
from pathlib import Path

from supplyguard.ingestion.chunker import chunk_element
from supplyguard.ingestion.parsers import parse_document
from supplyguard.retrieval.hybrid import lexical_score, tokens

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ((160, 30), (240, 40), (400, 60))
TOP_K = 6


def concept_tokens(text: str) -> set[str]:
    """Keep meaningful expected-answer words for transparent retrieval scoring."""
    stop = {"with", "from", "that", "this", "their", "across", "should"}
    return {word for word in tokens(text) if len(word) > 3 and word not in stop}


def score_case(question: str, expected: str, chunks: list) -> dict:
    """Measure whether top lexical chunks recover the expected answer concepts."""
    started = time.perf_counter()
    ranked = sorted(chunks, key=lambda chunk: lexical_score(question, chunk.text),
                    reverse=True)[:TOP_K]
    latency_ms = (time.perf_counter() - started) * 1000
    expected_terms = concept_tokens(expected)
    retrieved_terms = set(tokens(" ".join(chunk.text for chunk in ranked)))
    coverage = len(expected_terms & retrieved_terms) / max(1, len(expected_terms))
    relevant = [len(expected_terms & set(tokens(chunk.text))) >= 2 for chunk in ranked]
    reciprocal_rank = next((1 / rank for rank, hit in enumerate(relevant, 1) if hit), 0.0)
    return {"concept_recall_at_6": coverage, "hit_at_6": float(any(relevant)),
            "mrr_at_6": reciprocal_rank, "retrieval_latency_ms": latency_ms,
            "retrieved_context_words": sum(len(tokens(chunk.text)) for chunk in ranked)}


def main() -> None:
    """Run every candidate against document golden questions and write measured results."""
    elements = []
    for path in sorted((ROOT / "data/documents/public").glob("*.pdf")):
        elements.extend(parse_document(path))
    cases = [case for case in json.loads((ROOT / "evaluation.json").read_text())
             if case["category"] == "document"]
    rows = []
    for size, overlap in CANDIDATES:
        chunks = [chunk for element in elements
                  for chunk in chunk_element(element, "benchmark", size=size, overlap=overlap)]
        measurements = [score_case(case["question"], case["expected"], chunks)
                        for case in cases]
        rows.append({
            "chunk_words": size,
            "overlap_words": overlap,
            "chunk_count": len(chunks),
            "mean_concept_recall_at_6": sum(m["concept_recall_at_6"] for m in measurements) / len(measurements),
            "hit_rate_at_6": sum(m["hit_at_6"] for m in measurements) / len(measurements),
            "mean_reciprocal_rank_at_6": sum(m["mrr_at_6"] for m in measurements) / len(measurements),
            "mean_retrieval_latency_ms": sum(m["retrieval_latency_ms"] for m in measurements) / len(measurements),
            "mean_retrieved_context_words": sum(m["retrieved_context_words"] for m in measurements) / len(measurements),
        })
    output = ROOT / "chunking_benchmark.csv"
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(rows, indent=2))
    print(f"Wrote measured benchmark to {output}")


if __name__ == "__main__":
    main()
