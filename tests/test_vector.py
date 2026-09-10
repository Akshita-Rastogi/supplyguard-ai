from uuid import uuid4

import pytest
from qdrant_client import AsyncQdrantClient, models

from supplyguard.infrastructure.vector import VectorStore


@pytest.mark.asyncio
async def test_vector_search_cannot_cross_tenant_boundary():
    store = VectorStore("http://unused", "test_chunks")
    await store.client.close()
    store.client = AsyncQdrantClient(location=":memory:")
    await store.ensure_collection(3)
    tenant_a_id, tenant_b_id = str(uuid4()), str(uuid4())
    await store.upsert([
        models.PointStruct(id=tenant_a_id, vector=[1.0, 0.0, 0.0],
                           payload={"tenant_id": "tenant-a", "text": "allowed"}),
        models.PointStruct(id=tenant_b_id, vector=[1.0, 0.0, 0.0],
                           payload={"tenant_id": "tenant-b", "text": "secret"}),
    ])
    results = await store.search([1.0, 0.0, 0.0], "tenant-a")
    assert [point.payload["text"] for point in results] == ["allowed"]
    await store.close()


@pytest.mark.asyncio
async def test_vector_stats_reports_persisted_points():
    store = VectorStore("http://unused", "chunks")
    await store.client.close()
    store.client = AsyncQdrantClient(location=":memory:")
    await store.ensure_collection(2)
    await store.upsert([models.PointStruct(
        id=str(uuid4()), vector=[1.0, 0.0],
        payload={"tenant_id": "tenant-a", "source_id": "source"},
    )])
    assert await store.stats() == {"collection": "chunks", "exists": True, "vectors": 1}
    await store.close()
