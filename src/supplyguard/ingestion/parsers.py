from pathlib import Path

import pymupdf

from supplyguard.ingestion.models import PageElement


class UnsupportedDocument(ValueError):
    """Raised when a source cannot be safely parsed by the supported readers."""


def parse_markdown(path: Path) -> list[PageElement]:
    """Represent a UTF-8 text document as one page-level element."""
    return [PageElement(source_path=path, page=1, kind="text",
                        text=path.read_text(encoding="utf-8"), metadata={"format": "markdown"})]


def parse_pdf(path: Path) -> list[PageElement]:
    """Extract page text and tables while preserving non-extractable page signals."""
    elements = []
    with pymupdf.open(path) as document:
        if document.needs_pass:
            raise UnsupportedDocument(f"Encrypted PDF requires a password: {path.name}")
        for number, page in enumerate(document, 1):
            page_text = page.get_text("text", sort=True).strip()
            tables = page.find_tables().tables
            table_text = "\n".join(
                " | ".join("<NULL>" if value is None else str(value) for value in row)
                for table in tables for row in table.extract()
            )
            image_count = len(page.get_images(full=True))
            # Image presence is metadata; image-only pages remain visible as OCR work.
            metadata = {"format": "pdf", "page": number, "table_count": len(tables),
                        "image_count": image_count, "requires_ocr": not page_text and image_count > 0}
            if page_text:
                elements.append(PageElement(source_path=path, page=number, kind="text",
                                            text=page_text, metadata=metadata))
            if table_text:
                elements.append(PageElement(source_path=path, page=number, kind="table",
                                            text=f"TABLE DATA\n{table_text}", metadata=metadata))
            if not page_text and image_count:
                elements.append(PageElement(source_path=path, page=number, kind="ocr_required",
                    text="[Scanned image page: OCR or a local vision model is required]", metadata=metadata))
            elif not page_text:
                elements.append(PageElement(source_path=path, page=number, kind="blank_page",
                    text="[Blank or non-extractable page]", metadata=metadata))
    return elements


def parse_document(path: Path) -> list[PageElement]:
    """Dispatch a source to its parser and reject unknown formats explicitly."""
    if path.suffix.lower() == ".pdf":
        return parse_pdf(path)
    if path.suffix.lower() in {".md", ".txt"}:
        return parse_markdown(path)
    raise UnsupportedDocument(f"Unsupported extension: {path.suffix}")
