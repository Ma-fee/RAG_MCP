from __future__ import annotations

import pytest

from rag_mcp.ingestion.document_model import Chunk, Document, Element


def test_element_accepts_supported_types_only() -> None:
    ok = Element(
        element_id="el-1",
        element_type="text",
        text="hello",
        heading_path="Doc > Section",
        section_title="Section",
        section_level=1,
    )
    assert ok.element_type == "text"

    with pytest.raises(ValueError, match="element_type"):
        Element(
            element_id="el-2",
            element_type="unknown",
            text="bad",
            heading_path="Doc",
            section_title="Doc",
            section_level=0,
        )


def test_element_requires_non_negative_section_level() -> None:
    with pytest.raises(ValueError, match="section_level"):
        Element(
            element_id="el-3",
            element_type="text",
            text="x",
            heading_path="Doc",
            section_title="Doc",
            section_level=-1,
        )


def test_document_holds_ordered_elements() -> None:
    elements = [
        Element(
            element_id="h-1",
            element_type="heading",
            text="Intro",
            heading_path="Doc > Intro",
            section_title="Intro",
            section_level=1,
        ),
        Element(
            element_id="p-1",
            element_type="text",
            text="Paragraph",
            heading_path="Doc > Intro",
            section_title="Intro",
            section_level=1,
        ),
    ]
    doc = Document(
        doc_id="doc-1",
        title="Doc",
        relative_path="docs/doc.md",
        file_type="md",
        elements=elements,
    )
    assert [e.element_id for e in doc.elements] == ["h-1", "p-1"]


def test_chunk_contract_contains_source_element_ids_and_heading_context() -> None:
    chunk = Chunk(
        chunk_id="doc-1#chunk-0",
        doc_id="doc-1",
        text="Paragraph",
        chunk_index=0,
        source_element_ids=["p-1"],
        heading_path="Doc > Intro",
        section_title="Intro",
        section_level=1,
        title="Doc",
        file_type="md",
        relative_path="docs/doc.md",
    )
    assert chunk.source_element_ids == ["p-1"]
    assert chunk.heading_path == "Doc > Intro"
    assert chunk.section_level == 1
