import hashlib
from uuid import NAMESPACE_URL, uuid5

from supplyguard.ingestion.models import Chunk, PageElement


def chunk_element(element: PageElement, tenant_id: str, size: int = 160, overlap: int = 30):
    """Split one page element into overlapping, reproducibly identified chunks."""
    words = element.text.split()
    if not words:
        return []
    chunks = []
    source_id = hashlib.sha256(str(element.source_path).encode()).hexdigest()[:16]
    # Step size preserves the requested overlap without duplicating an entire chunk.
    for ordinal, start in enumerate(range(0, len(words), size - overlap)):
        body = " ".join(words[start:start + size])
        locator = f"page:{element.page}:{element.kind}:chunk:{ordinal}"
        point_id = str(uuid5(NAMESPACE_URL, f"{tenant_id}:{source_id}:{locator}"))
        # Tenant participates in the UUID so identical files cannot collide across tenants.
        chunks.append(Chunk(source_id=source_id, point_id=point_id,
            title=element.source_path.stem.replace("_", " ").title(), text=body,
            ordinal=ordinal, locator=locator,
            metadata={**element.metadata, "element_kind": element.kind},
            content_hash=hashlib.sha256(body.encode()).hexdigest()))
    return chunks
