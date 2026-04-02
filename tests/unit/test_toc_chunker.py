from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from rag_mcp.chunking.toc_chunker import (
    TocAwareChunker,
    _TocNode,
    _assemble_text,
    _extract_toc_nodes,
)
from rag_mcp.ingestion.document_model import Element
from rag_mcp.models import SourceDocument


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_element(element_id, element_type, text, page, extra_meta=None):
    meta = {"page_number": page}
    if extra_meta:
        meta.update(extra_meta)
    return Element(
        element_id=element_id,
        element_type=element_type,
        text=text,
        heading_path="Root",
        section_title="Root",
        section_level=0,
        metadata=meta,
    )


def _make_doc(elements):
    return SourceDocument(
        doc_id="doc-1",
        title="Test Manual",
        relative_path="manual.pdf",
        file_type="pdf",
        text="",
        elements=elements,
    )


# ---------------------------------------------------------------------------
# _assemble_text
# ---------------------------------------------------------------------------

def test_assemble_text_combines_heading_and_text():
    elements = [
        _make_element("e1", "heading", "Chapter 1", 1),
        _make_element("e2", "text", "Some body text.", 1),
    ]
    result = _assemble_text(elements)
    assert "Chapter 1" in result
    assert "Some body text." in result


def test_assemble_text_skips_table_markdown():
    elements = [
        _make_element("e1", "table", "", 1, extra_meta={"markdown": "| a | b |\n|---|---|\n| 1 | 2 |"}),
    ]
    result = _assemble_text(elements)
    assert result == ""


def test_assemble_text_skips_table_text_when_no_markdown():
    elements = [
        _make_element("e1", "table", "fallback text", 1),
    ]
    result = _assemble_text(elements)
    assert result == ""


def test_assemble_text_skips_image_elements():
    elements = [
        _make_element("e1", "image", "base64data", 1),
        _make_element("e2", "text", "real content", 1),
    ]
    result = _assemble_text(elements)
    assert "base64data" not in result
    assert "real content" in result


def test_assemble_text_empty_returns_empty_string():
    assert _assemble_text([]) == ""


# ---------------------------------------------------------------------------
# _extract_toc_nodes — fitz not available
# ---------------------------------------------------------------------------

def test_extract_toc_nodes_returns_empty_when_fitz_missing(monkeypatch):
    import builtins
    real_import = builtins.__import__

    def blocked_import(name, *args, **kwargs):
        if name == "fitz":
            raise ImportError("fitz not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked_import)
    nodes = _extract_toc_nodes(Path("dummy.pdf"))
    assert nodes == []


# ---------------------------------------------------------------------------
# _extract_toc_nodes — mocked fitz
# ---------------------------------------------------------------------------

def _make_fitz_doc(toc, page_count):
    mock_doc = MagicMock()
    mock_doc.get_toc.return_value = toc
    mock_doc.page_count = page_count
    return mock_doc


def test_extract_toc_nodes_returns_empty_when_no_toc(monkeypatch):
    mock_fitz = MagicMock()
    mock_fitz.open.return_value = _make_fitz_doc([], 100)
    monkeypatch.setitem(__import__("sys").modules, "fitz", mock_fitz)

    nodes = _extract_toc_nodes(Path("dummy.pdf"))
    assert nodes == []


def test_extract_toc_nodes_single_entry_page_end_is_total(monkeypatch):
    toc = [(1, "Chapter 1", 5)]
    mock_fitz = MagicMock()
    mock_fitz.open.return_value = _make_fitz_doc(toc, 100)
    monkeypatch.setitem(__import__("sys").modules, "fitz", mock_fitz)

    nodes = _extract_toc_nodes(Path("dummy.pdf"))
    assert len(nodes) == 1
    assert nodes[0].title == "Chapter 1"
    assert nodes[0].page_start == 5
    assert nodes[0].page_end == 100


def test_extract_toc_nodes_page_end_is_next_start_minus_one(monkeypatch):
    toc = [
        (1, "Chapter 1", 5),
        (1, "Chapter 2", 20),
    ]
    mock_fitz = MagicMock()
    mock_fitz.open.return_value = _make_fitz_doc(toc, 100)
    monkeypatch.setitem(__import__("sys").modules, "fitz", mock_fitz)

    nodes = _extract_toc_nodes(Path("dummy.pdf"))
    assert nodes[0].page_end == 19
    assert nodes[1].page_end == 100


def test_extract_toc_nodes_builds_nested_heading_path(monkeypatch):
    toc = [
        (1, "Part I", 1),
        (2, "Chapter 1", 5),
        (3, "Section 1.1", 7),
    ]
    mock_fitz = MagicMock()
    mock_fitz.open.return_value = _make_fitz_doc(toc, 50)
    monkeypatch.setitem(__import__("sys").modules, "fitz", mock_fitz)

    nodes = _extract_toc_nodes(Path("dummy.pdf"))
    assert nodes[0].heading_path == "Part I"
    assert nodes[1].heading_path == "Part I > Chapter 1"
    assert nodes[2].heading_path == "Part I > Chapter 1 > Section 1.1"


def test_extract_toc_nodes_skips_blank_titles(monkeypatch):
    toc = [
        (1, "", 1),
        (1, "  ", 3),
        (1, "Real Chapter", 5),
    ]
    mock_fitz = MagicMock()
    mock_fitz.open.return_value = _make_fitz_doc(toc, 50)
    monkeypatch.setitem(__import__("sys").modules, "fitz", mock_fitz)

    nodes = _extract_toc_nodes(Path("dummy.pdf"))
    assert len(nodes) == 1
    assert nodes[0].title == "Real Chapter"


def test_extract_toc_nodes_resets_child_ancestors_on_level_up(monkeypatch):
    toc = [
        (1, "Part I", 1),
        (2, "Chapter 1", 3),
        (1, "Part II", 10),
    ]
    mock_fitz = MagicMock()
    mock_fitz.open.return_value = _make_fitz_doc(toc, 50)
    monkeypatch.setitem(__import__("sys").modules, "fitz", mock_fitz)

    nodes = _extract_toc_nodes(Path("dummy.pdf"))
    assert nodes[2].heading_path == "Part II"


# ---------------------------------------------------------------------------
# TocAwareChunker.chunk_document
# ---------------------------------------------------------------------------

def _nodes_to_patch(nodes):
    return patch(
        "rag_mcp.chunking.toc_chunker._extract_toc_nodes",
        return_value=nodes,
    )


def test_chunk_document_returns_empty_when_no_toc():
    with patch("rag_mcp.chunking.toc_chunker._extract_toc_nodes", return_value=[]):
        chunker = TocAwareChunker()
        doc = _make_doc([])
        result = chunker.chunk_document(doc, Path("dummy.pdf"))
    assert result == []


def test_chunk_document_basic_chunk_fields():
    nodes = [
        _TocNode(level=1, title="Chapter 1", heading_path="Chapter 1", page_start=1, page_end=5),
    ]
    elements = [
        _make_element("e1", "text", "Body text for chapter one with more words.", 2),
    ]
    doc = _make_doc(elements)

    with _nodes_to_patch(nodes):
        chunks = TocAwareChunker().chunk_document(doc, Path("dummy.pdf"))

    assert len(chunks) == 1
    c = chunks[0]
    assert c.doc_id == "doc-1"
    assert c.chunk_id == "doc-1#toc-0"
    assert c.section_title == "Chapter 1"
    assert c.heading_path == "Chapter 1"
    assert c.section_level == 1
    assert c.metadata["page_start"] == 1
    assert c.metadata["page_end"] == 5
    assert c.metadata["toc_level"] == 1
    assert "Body text for chapter one with more words." in c.text


def test_chunk_document_filters_short_chunks():
    nodes = [
        _TocNode(level=1, title="Short", heading_path="Short", page_start=1, page_end=1),
        _TocNode(level=1, title="Long", heading_path="Long", page_start=2, page_end=5),
    ]
    elements = [
        _make_element("e1", "text", "Hi", 1),
        _make_element("e2", "text", "This is a much longer body paragraph.", 3),
    ]
    doc = _make_doc(elements)

    with _nodes_to_patch(nodes):
        chunks = TocAwareChunker(min_chunk_length=20).chunk_document(doc, Path("dummy.pdf"))

    assert len(chunks) == 1
    assert chunks[0].section_title == "Long"


def test_chunk_document_assigns_sequential_indices():
    nodes = [
        _TocNode(level=1, title="A", heading_path="A", page_start=1, page_end=2),
        _TocNode(level=1, title="B", heading_path="B", page_start=3, page_end=4),
        _TocNode(level=1, title="C", heading_path="C", page_start=5, page_end=6),
    ]
    elements = [
        _make_element("e1", "text", "Content for section A with enough text.", 1),
        _make_element("e2", "text", "Content for section B with enough text.", 3),
        _make_element("e3", "text", "Content for section C with enough text.", 5),
    ]
    doc = _make_doc(elements)

    with _nodes_to_patch(nodes):
        chunks = TocAwareChunker().chunk_document(doc, Path("dummy.pdf"))

    assert [c.chunk_index for c in chunks] == [0, 1, 2]
    assert [c.chunk_id for c in chunks] == [
        "doc-1#toc-0",
        "doc-1#toc-1",
        "doc-1#toc-2",
    ]


def test_chunk_document_assigns_elements_by_page_range():
    nodes = [
        _TocNode(level=1, title="Chap1", heading_path="Chap1", page_start=1, page_end=3),
        _TocNode(level=1, title="Chap2", heading_path="Chap2", page_start=4, page_end=6),
    ]
    elements = [
        _make_element("e1", "text", "Chapter 1 paragraph one two three.", 2),
        _make_element("e2", "text", "Chapter 2 paragraph one two three.", 5),
    ]
    doc = _make_doc(elements)

    with _nodes_to_patch(nodes):
        chunks = TocAwareChunker().chunk_document(doc, Path("dummy.pdf"))

    assert len(chunks) == 2
    assert "Chapter 1" in chunks[0].text
    assert "Chapter 2" in chunks[1].text
    assert "Chapter 2" not in chunks[0].text
    assert "Chapter 1" not in chunks[1].text


def test_chunk_document_source_element_ids_populated():
    nodes = [
        _TocNode(level=2, title="Sec", heading_path="Sec", page_start=1, page_end=2),
    ]
    elements = [
        _make_element("elem-A", "text", "Some sufficiently long body text here.", 1),
        _make_element("elem-B", "heading", "Sub-heading", 1),
    ]
    doc = _make_doc(elements)

    with _nodes_to_patch(nodes):
        chunks = TocAwareChunker().chunk_document(doc, Path("dummy.pdf"))

    assert set(chunks[0].source_element_ids) == {"elem-A", "elem-B"}


def test_chunk_document_empty_section_not_included():
    """A TOC node with no matching elements produces no chunk."""
    nodes = [
        _TocNode(level=1, title="Ghost", heading_path="Ghost", page_start=10, page_end=15),
    ]
    elements = [
        _make_element("e1", "text", "Unrelated content on page 1.", 1),
    ]
    doc = _make_doc(elements)

    with _nodes_to_patch(nodes):
        chunks = TocAwareChunker(min_chunk_length=1).chunk_document(doc, Path("dummy.pdf"))

    assert chunks == []
