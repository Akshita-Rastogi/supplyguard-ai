"""Idempotently load documents and public-data snapshots into MongoDB."""
import asyncio
import csv
from pathlib import Path

from pymongo import AsyncMongoClient, UpdateOne
from qdrant_client import models

from supplyguard.core.config import get_settings
from supplyguard.infrastructure.ollama import OllamaClient
from supplyguard.infrastructure.vector import VectorStore
from supplyguard.ingestion.chunker import chunk_element
from supplyguard.ingestion.parsers import UnsupportedDocument, parse_document

ROOT = Path(__file__).resolve().parents[1]
TENANT = "demo-corp"


async def main():
    """Parse, embed, and idempotently store the public document and CSV corpus."""
    settings = get_settings()
    client = AsyncMongoClient(settings.mongodb_uri)
    db = client[settings.mongodb_database]
    ollama = OllamaClient(settings.ollama_base_url, settings.ollama_chat_model,
                          settings.ollama_embed_model)
    vectors = VectorStore(settings.qdrant_url, settings.qdrant_collection)
    all_chunks = []
    failures = []
    paths = sorted((ROOT / "data/documents/public").glob("*.pdf"))
    for path in paths:
        try:
            elements = parse_document(path)
        except (UnsupportedDocument, OSError, RuntimeError, ValueError) as exc:
            failures.append({"source": str(path), "error_type": type(exc).__name__})
            continue
        for element in elements:
            for chunk in chunk_element(element, TENANT):
                row = {"tenant_id": TENANT, **chunk.model_dump(mode="json")}
                await db.chunks.update_one(
                    {"tenant_id": TENANT, "point_id": chunk.point_id},
                    {"$set": row}, upsert=True)
                all_chunks.append(row)
    embeddings = await ollama.embed_batched([row["text"] for row in all_chunks])
    # Embedding dimensionality comes from the model, avoiding a duplicated constant.
    if embeddings:
        await vectors.ensure_collection(len(embeddings[0]))
        points = [models.PointStruct(id=row["point_id"], vector=vector, payload=row)
                  for row, vector in zip(all_chunks, embeddings, strict=True)]
        for start in range(0, len(points), 128):
            await vectors.upsert(points[start:start + 128])
    record_operations = []
    with (ROOT / "data/raw/public/fema_disaster_declarations_full.csv").open(
            encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            # Stable source IDs and bulk upserts keep repeated ingestion fast and idempotent.
            row.update({"tenant_id": TENANT, "record_type": "fema_declaration",
                        "record_id": row["id"], "disasterNumber": int(row["disasterNumber"]),
                        "fyDeclared": int(row["fyDeclared"])})
            record_operations.append(UpdateOne(
                {"tenant_id": TENANT, "record_id": row["record_id"]},
                {"$set": row}, upsert=True,
            ))
            if len(record_operations) == 1000:
                await db.records.bulk_write(record_operations, ordered=False)
                record_operations.clear()
    if record_operations:
        await db.records.bulk_write(record_operations, ordered=False)
    await db.ingestion_runs.insert_one({"tenant_id": TENANT, "documents": len(paths),
        "chunks": len(all_chunks), "failures": failures,
        "embedding_model": settings.ollama_embed_model})
    print(f"Seed completed: {len(paths)} documents, {len(all_chunks)} chunks, {len(failures)} failures")
    await ollama.close()
    await vectors.close()
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
