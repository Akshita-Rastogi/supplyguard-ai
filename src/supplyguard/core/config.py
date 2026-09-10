from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central, environment-overridable runtime configuration."""
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: str = "development"
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_database: str = "supplyguard"
    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "mistral:instruct"
    ollama_embed_model: str = "nomic-embed-text"
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "supplyguard_chunks_v1"
    mcp_server_url: str = "http://localhost:8001/mcp"
    min_evidence_score: float = 0.35
    api_keys: str = "demo-key:analyst,admin-key:admin"
    request_timeout_seconds: float = 12.0
    max_question_chars: int = 2000
    max_context_chars: int = 12000
    memory_max_turns: int = 6
    memory_max_chars: int = 4000
    memory_ttl_hours: int = 24

    def key_roles(self) -> dict[str, str]:
        """Convert the compact environment setting into an API-key-to-role map."""
        return dict(item.split(":", 1) for item in self.api_keys.split(",") if ":" in item)


@lru_cache
def get_settings() -> Settings:
    """Build settings once so all components share an identical configuration."""
    return Settings()
