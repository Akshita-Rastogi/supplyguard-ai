from pathlib import Path

from supplyguard.ingestion.chunker import chunk_element
from supplyguard.ingestion.parsers import parse_pdf

ROOT = Path(__file__).resolve().parents[1]


def test_mixed_pdf_extracts_tables_image_and_page_locators():
    elements = parse_pdf(ROOT / "data/documents/public/world_bank_contract_management_2024.pdf")
    assert any(element.metadata["table_count"] >= 1 for element in elements)
    assert any(element.metadata["image_count"] >= 1 for element in elements)
    chunks = [chunk for element in elements for chunk in chunk_element(element, "tenant-a")]
    assert any(":table:chunk:" in chunk.locator for chunk in chunks)
    assert all(chunk.metadata["format"] == "pdf" for chunk in chunks)


def test_chunk_ids_are_deterministic_and_tenant_specific():
    element = parse_pdf(ROOT / "data/documents/public/world_bank_procurement_regulations_2025.pdf")[0]
    first = chunk_element(element, "tenant-a")[0]
    repeated = chunk_element(element, "tenant-a")[0]
    other_tenant = chunk_element(element, "tenant-b")[0]
    assert first.point_id == repeated.point_id
    assert first.point_id != other_tenant.point_id
