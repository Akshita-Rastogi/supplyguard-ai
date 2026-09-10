from qdrant_client import AsyncQdrantClient, models


class VectorStoreError(RuntimeError):
    """Stable application error for Qdrant query failures."""


class VectorStore:
    """Qdrant adapter that enforces tenant filtering on every search."""

    def __init__(self, url: str, collection: str):
        """Create an asynchronous client for one versioned vector collection."""
        self.client = AsyncQdrantClient(url=url, timeout=10)
        self.collection = collection

    async def ensure_collection(self, dimensions: int) -> None:
        """Create the cosine collection and tenant payload index when absent."""
        if not await self.client.collection_exists(self.collection):
            await self.client.create_collection(
                self.collection,
                vectors_config=models.VectorParams(size=dimensions, distance=models.Distance.COSINE),
            )
            await self.client.create_payload_index(
                self.collection, "tenant_id", models.PayloadSchemaType.KEYWORD
            )

    async def upsert(self, points: list[models.PointStruct]) -> None:
        """Persist a non-empty point batch and wait until it is searchable."""
        if points:
            await self.client.upsert(self.collection, points=points, wait=True)

    async def search(self, vector: list[float], tenant_id: str, filters: dict | None = None,
                     limit: int = 10):
        """Run tenant-scoped dense search with optional allowlisted metadata filters."""
        conditions = [models.FieldCondition(
            key="tenant_id", match=models.MatchValue(value=tenant_id))]
        conditions.extend(models.FieldCondition(
            key=f"metadata.{key}", match=models.MatchValue(value=value))
            for key, value in (filters or {}).items())
        try:
            result = await self.client.query_points(
                collection_name=self.collection,
                query=vector,
                query_filter=models.Filter(must=conditions),
                limit=limit,
                with_payload=True,
            )
            return result.points
        except Exception as exc:  # Normalize transport and client-version errors.
            raise VectorStoreError(f"Vector search unavailable: {type(exc).__name__}") from exc

    async def ready(self) -> bool:
        """Collapse any Qdrant client failure into a readiness boolean."""
        try:
            await self.client.get_collections()
            return True
        except Exception:  # noqa: BLE001 - readiness must collapse all client failures to false
            return False

    async def stats(self) -> dict:
        """Return collection existence and persisted vector count for inspection."""
        try:
            if not await self.client.collection_exists(self.collection):
                return {"collection": self.collection, "exists": False, "vectors": 0}
            info = await self.client.get_collection(self.collection)
            return {"collection": self.collection, "exists": True,
                    "vectors": info.points_count or 0}
        except Exception as exc:  # Normalize Qdrant transport and client failures.
            raise VectorStoreError(f"Vector statistics unavailable: {type(exc).__name__}") from exc

    async def close(self) -> None:
        """Release Qdrant HTTP resources during application shutdown."""
        await self.client.close()
