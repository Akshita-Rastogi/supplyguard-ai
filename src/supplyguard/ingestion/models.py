from pathlib import Path

from pydantic import BaseModel, Field


class PageElement(BaseModel):
    """One page-level text, table, OCR marker, or blank-page element."""
    source_path: Path
    page: int
    kind: str
    text: str
    metadata: dict = Field(default_factory=dict)


class Chunk(BaseModel):
    """Deterministic retrieval unit shared by MongoDB and Qdrant."""
    source_id: str
    point_id: str
    title: str
    text: str
    ordinal: int
    locator: str
    metadata: dict
    content_hash: str
