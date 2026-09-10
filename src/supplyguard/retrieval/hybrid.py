import math
import re
from collections import Counter

from supplyguard.domain.models import Citation


def tokens(text: str) -> list[str]:
    """Normalize text into deterministic alphanumeric lexical tokens."""
    return re.findall(r"[a-z0-9]+", text.lower())


def lexical_score(query: str, text: str) -> float:
    """Measure term-frequency cosine similarity for the lightweight lexical path."""
    q, d = Counter(tokens(query)), Counter(tokens(text))
    if not q or not d:
        return 0.0
    dot = sum(q[t] * d[t] for t in q)
    norm = math.sqrt(sum(v * v for v in q.values()) * sum(v * v for v in d.values()))
    return dot / norm if norm else 0.0


async def retrieve(db, vectors, ollama, tenant_id: str, query: str, filters: dict,
                   limit: int = 6) -> list[Citation]:
    """Fuse Qdrant dense rank and inspectable lexical rank with reciprocal-rank fusion."""
    selector = {"tenant_id": tenant_id, **{f"metadata.{k}": v for k, v in filters.items()}}
    # The public corpus currently creates 2,198 chunks; the safety cap must cover all of it.
    rows = [row async for row in db.chunks.find(selector, {"embedding": 0}).limit(10000)]
    lexical = sorted((r for r in rows if lexical_score(query, r["text"]) > 0),
                     key=lambda r: lexical_score(query, r["text"]), reverse=True)[:20]
    query_vector = (await ollama.embeddings([query]))[0]
    dense = await vectors.search(query_vector, tenant_id, filters=filters, limit=20)
    fused: dict[str, float] = {}
    documents = {row["point_id"]: row for row in rows}
    # RRF combines ranks rather than incomparable dense and lexical raw scores.
    for rank, row in enumerate(lexical, 1):
        fused[row["point_id"]] = fused.get(row["point_id"], 0) + 1 / (60 + rank)
    for rank, hit in enumerate(dense, 1):
        point_id = str(hit.id)
        fused[point_id] = fused.get(point_id, 0) + 1 / (60 + rank)
        if point_id not in documents and hit.payload:
            documents[point_id] = hit.payload
    ranked = sorted(fused, key=fused.get, reverse=True)[:limit]
    max_rrf = 2 / 61
    return [Citation(source_id=documents[key]["source_id"], title=documents[key]["title"],
        locator=documents[key].get("locator", f"chunk:{documents[key]['ordinal']}"),
        excerpt=documents[key]["text"][:700], score=min(fused[key] / max_rrf, 1.0))
        for key in ranked if key in documents]
