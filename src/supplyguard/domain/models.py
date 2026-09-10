from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class Intent(str, Enum):
    """Supported execution paths selected by the intent router."""
    DOCUMENT = "document"
    ANALYTICS = "analytics"
    LIVE_RISK = "live_risk"
    UNSUPPORTED = "unsupported"


class Citation(BaseModel):
    """Evidence returned independently of model-generated citation text."""
    source_id: str
    title: str
    locator: str
    excerpt: str
    score: float = Field(ge=0, le=1)


class AskRequest(BaseModel):
    """Validated public contract for an assistant question."""
    question: str = Field(min_length=3, max_length=2000)
    tenant_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{2,64}$")
    conversation_id: str | None = Field(
        default=None, pattern=r"^[a-zA-Z0-9_-]{8,64}$"
    )
    filters: dict[str, str | int | float | bool] = Field(default_factory=dict)

    @field_validator("question")
    @classmethod
    def reject_control_chars(cls, value: str) -> str:
        """Normalize harmless whitespace and reject invisible control characters."""
        cleaned = " ".join(value.split())
        if any(ord(c) < 32 for c in cleaned):
            raise ValueError("control characters are not allowed")
        return cleaned


class AskResponse(BaseModel):
    """Inspectable answer contract including evidence and execution metadata."""
    request_id: str
    answer: str
    intent: Intent
    confidence: float = Field(ge=0, le=1)
    citations: list[Citation]
    tool_trace: list[dict]
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class FeedbackRequest(BaseModel):
    """Explicit user evaluation associated with one prior request."""
    request_id: str
    helpful: bool
    reason: str | None = Field(default=None, max_length=1000)
