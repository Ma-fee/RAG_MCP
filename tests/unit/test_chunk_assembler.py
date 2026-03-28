from __future__ import annotations

from rag_mcp.ingestion.document_model import Element
from rag_mcp.models import SourceDocument


def _doc_with_elements(elements: list[Element]) -> SourceDocument:
    return SourceDocument(
        doc_id="doc-1",
        title="spec.md",
        relative_path="spec.md",
        file_type="md",
        text="",
        elements=elements,
    )


def test_chunk_assembler_merges_adjacent_text_in_same_context() -> None:
    from rag_mcp.chunking.assembler import ChunkAssembler

    doc = _doc_with_elements(
        [
            Element(
                element_id="h-1",
                element_type="heading",
                text="Intro",
                heading_path="Doc > Intro",
                section_title="Intro",
                section_level=1,
            ),
            Element(
                element_id="t-1",
                element_type="text",
                text="alpha one",
                heading_path="Doc > Intro",
                section_title="Intro",
                section_level=1,
            ),
            Element(
                element_id="t-2",
                element_type="text",
                text="beta two",
                heading_path="Doc > Intro",
                section_title="Intro",
                section_level=1,
            ),
        ]
    )

    chunks = ChunkAssembler(chunk_size=64, chunk_overlap=8).assemble(doc)

    assert len(chunks) == 1
    assert chunks[0].text == "alpha one beta two"
    assert chunks[0].source_element_ids == ["t-1", "t-2"]
    assert chunks[0].heading_path == "Doc > Intro"


def test_chunk_assembler_never_merges_across_heading_context() -> None:
    from rag_mcp.chunking.assembler import ChunkAssembler

    doc = _doc_with_elements(
        [
            Element(
                element_id="h-1",
                element_type="heading",
                text="Intro",
                heading_path="Doc > Intro",
                section_title="Intro",
                section_level=1,
            ),
            Element(
                element_id="t-1",
                element_type="text",
                text="intro section",
                heading_path="Doc > Intro",
                section_title="Intro",
                section_level=1,
            ),
            Element(
                element_id="h-2",
                element_type="heading",
                text="Design",
                heading_path="Doc > Design",
                section_title="Design",
                section_level=1,
            ),
            Element(
                element_id="t-2",
                element_type="text",
                text="design section",
                heading_path="Doc > Design",
                section_title="Design",
                section_level=1,
            ),
        ]
    )

    chunks = ChunkAssembler(chunk_size=256, chunk_overlap=16).assemble(doc)

    assert len(chunks) == 2
    assert chunks[0].source_element_ids == ["t-1"]
    assert chunks[1].source_element_ids == ["t-2"]
    assert chunks[0].heading_path == "Doc > Intro"
    assert chunks[1].heading_path == "Doc > Design"


def test_chunk_assembler_applies_overlap_within_same_context() -> None:
    from rag_mcp.chunking.assembler import ChunkAssembler

    long_text = "abcdefghijklmnopqrstuvwxyz0123456789"
    doc = _doc_with_elements(
        [
            Element(
                element_id="t-1",
                element_type="text",
                text=long_text,
                heading_path="Doc",
                section_title="Doc",
                section_level=0,
            )
        ]
    )

    chunks = ChunkAssembler(chunk_size=16, chunk_overlap=4).assemble(doc)

    assert len(chunks) >= 2
    assert chunks[0].text[-4:] == chunks[1].text[:4]
    assert all(chunk.heading_path == "Doc" for chunk in chunks)
    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))
