from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import PyMongoError

from supplyguard.core.config import Settings


class Mongo:
    """Own the MongoDB connection, indexes, and readiness boundary."""

    def __init__(self, settings: Settings):
        """Create a lazy Motor client; network access starts on the first operation."""
        self.settings = settings
        self.client = AsyncMongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=3000)
        self.db: AsyncDatabase = self.client[settings.mongodb_database]

    async def ensure_indexes(self) -> None:
        """Create uniqueness, lookup, audit-retention, and session-expiry indexes."""
        await self.db.chunks.create_index([("tenant_id", 1), ("point_id", 1)], unique=True)
        await self.db.chunks.create_index([("tenant_id", 1), ("source_id", 1), ("locator", 1)])
        await self.db.records.create_index([("tenant_id", 1), ("record_type", 1)])
        await self.db.audit_events.create_index("created_at", expireAfterSeconds=60 * 60 * 24 * 90)
        await self.db.feedback.create_index("request_id", unique=True)
        await self.db.conversation_turns.create_index(
            [("tenant_id", 1), ("conversation_id", 1), ("created_at", -1)]
        )
        await self.db.conversation_turns.create_index(
            "created_at", expireAfterSeconds=60 * 60 * self.settings.memory_ttl_hours
        )

    async def ready(self) -> bool:
        """Return a boolean health result instead of leaking driver exceptions."""
        try:
            await self.client.admin.command("ping")
            return True
        except PyMongoError:
            return False
