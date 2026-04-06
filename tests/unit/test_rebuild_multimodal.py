from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from rag_mcp.ingestion.document_model import Element
from rag_mcp.indexing.rebuild import rebuild_keyword_index
from rag_mcp.models import Chunk, SourceDocument


def _make_pdf_doc(elements: list[Element], relative_path: str = "manual.pdf") -> SourceDocument:
    return SourceDocument(
        doc_id="pdf-doc",
        title=relative_path,
        relative_path=relative_path,
        file_type="pdf",
        text=" ".join(e.text for e in elements).strip(),
        elements=elements,
    )


def _make_toc_chunks(doc: SourceDocument, source_element_ids: list[str], text: str = "toc chunk text") -> list[Chunk]:
    return [
        Chunk(
            chunk_id=f"{doc.doc_id}#toc-0",
            doc_id=doc.doc_id,
            text=text,
            chunk_index=0,
            source_element_ids=source_element_ids,
            heading_path="1 Intro",
            section_title="1 Intro",
            section_level=1,
            title=doc.title,
            file_type="pdf",
            relative_path=doc.relative_path,
            metadata={"page_start": 1, "page_end": 1, "toc_level": 1},
        )
    ]


def test_rebuild_creates_resource_store_json(tmp_path: Path) -> None:
    corpus_dir = tmp_path / "corpus"
    data_dir = tmp_path / "data"
    corpus_dir.mkdir(parents=True)
    (corpus_dir / "manual.pdf").write_bytes(b"%PDF-1.4")

    elements = [
        Element(
            element_id="el-0",
            element_type="text",
            text="hello world",
            heading_path="1 Intro",
            section_title="1 Intro",
            section_level=1,
            metadata={"page_number": 1},
        )
    ]
    pdf_doc = _make_pdf_doc(elements)

    with (
        patch("rag_mcp.indexing.rebuild.load_supported_documents", return_value=[pdf_doc]),
        patch("rag_mcp.indexing.rebuild.TocAwareChunker.chunk_document", return_value=_make_toc_chunks(pdf_doc, ["el-0"])),
    ):
        rebuild_keyword_index(source_dir=corpus_dir, data_dir=data_dir)

    manifest = json.loads((data_dir / "active_index.json").read_text())
    index_dir = Path(manifest["index_dir"])
    assert (index_dir / "resource_store.json").exists()


def test_rebuild_resource_store_has_text_entries(tmp_path: Path) -> None:
    corpus_dir = tmp_path / "corpus"
    data_dir = tmp_path / "data"
    corpus_dir.mkdir(parents=True)
    (corpus_dir / "manual.pdf").write_bytes(b"%PDF-1.4")

    elements = [
        Element(
            element_id="el-0",
            element_type="text",
            text="hello world",
            heading_path="1 Intro",
            section_title="1 Intro",
            section_level=1,
            metadata={"page_number": 1},
        )
    ]
    pdf_doc = _make_pdf_doc(elements)

    with (
        patch("rag_mcp.indexing.rebuild.load_supported_documents", return_value=[pdf_doc]),
        patch("rag_mcp.indexing.rebuild.TocAwareChunker.chunk_document", return_value=_make_toc_chunks(pdf_doc, ["el-0"])),
    ):
        rebuild_keyword_index(source_dir=corpus_dir, data_dir=data_dir)

    manifest = json.loads((data_dir / "active_index.json").read_text())
    index_dir = Path(manifest["index_dir"])
    store = json.loads((index_dir / "resource_store.json").read_text())

    text_entries = [e for e in store["entries"] if e["type"] == "text"]
    assert text_entries
    for entry in text_entries:
        assert "#text-" in entry["uri"]


def test_rebuild_keyword_store_uri_uses_text_prefix(tmp_path: Path) -> None:
    corpus_dir = tmp_path / "corpus"
    data_dir = tmp_path / "data"
    corpus_dir.mkdir(parents=True)
    (corpus_dir / "manual.pdf").write_bytes(b"%PDF-1.4")

    elements = [
        Element(
            element_id="el-0",
            element_type="text",
            text="hello world",
            heading_path="1 Intro",
            section_title="1 Intro",
            section_level=1,
            metadata={"page_number": 1},
        )
    ]
    pdf_doc = _make_pdf_doc(elements)

    with (
        patch("rag_mcp.indexing.rebuild.load_supported_documents", return_value=[pdf_doc]),
        patch("rag_mcp.indexing.rebuild.TocAwareChunker.chunk_document", return_value=_make_toc_chunks(pdf_doc, ["el-0"])),
    ):
        rebuild_keyword_index(source_dir=corpus_dir, data_dir=data_dir)

    manifest = json.loads((data_dir / "active_index.json").read_text())
    index_dir = Path(manifest["index_dir"])
    kw_store = json.loads((index_dir / "keyword_store.json").read_text())

    for entry in kw_store["entries"]:
        assert "#text-" in entry["uri"], f"Expected #text- in URI, got: {entry['uri']}"
        assert "#chunk-" not in entry["uri"]


def test_rebuild_passes_vlm_client_to_resource_store(tmp_path: Path) -> None:
    corpus_dir = tmp_path / "corpus"
    data_dir = tmp_path / "data"
    corpus_dir.mkdir(parents=True)
    (corpus_dir / "manual.pdf").write_bytes(b"%PDF-1.4")

    elements = [
        Element(
            element_id="el-0",
            element_type="text",
            text="hello world",
            heading_path="1 Intro",
            section_title="1 Intro",
            section_level=1,
            metadata={"page_number": 1},
        )
    ]
    pdf_doc = _make_pdf_doc(elements)

    mock_vlm = MagicMock()
    with (
        patch("rag_mcp.indexing.rebuild.load_supported_documents", return_value=[pdf_doc]),
        patch("rag_mcp.indexing.rebuild.TocAwareChunker.chunk_document", return_value=_make_toc_chunks(pdf_doc, ["el-0"])),
    ):
        rebuild_keyword_index(source_dir=corpus_dir, data_dir=data_dir, vlm_client=mock_vlm)

    # vlm_client.describe_image should not be called (no images in md file)
    mock_vlm.describe_image.assert_not_called()


def test_rebuild_table_entry_has_related_chunk_uri(tmp_path: Path) -> None:
    corpus_dir = tmp_path / "corpus"
    data_dir = tmp_path / "data"
    corpus_dir.mkdir(parents=True)

    elements = [
        Element(
            element_id="el-0",
            element_type="text",
            text="The following table shows specifications.",
            heading_path="Doc > Section",
            section_title="Section",
            section_level=1,
        ),
        Element(
            element_id="el-1",
            element_type="table",
            text="",
            heading_path="Doc > Section",
            section_title="Section",
            section_level=1,
            metadata={"markdown": "| A | B |\n|---|---|\n| 1 | 2 |", "data_json": "", "caption": ""},
        ),
    ]
    fake_doc = SourceDocument(
        doc_id="abc123",
        title="manual.pdf",
        relative_path="manual.pdf",
        file_type="pdf",
        text="The following table shows specifications.",
        elements=elements,
    )
    (corpus_dir / "manual.pdf").write_bytes(b"%PDF-1.4")

    with (
        patch("rag_mcp.indexing.rebuild.load_supported_documents", return_value=[fake_doc]),
        patch(
            "rag_mcp.indexing.rebuild.TocAwareChunker.chunk_document",
            return_value=_make_toc_chunks(fake_doc, ["el-0", "el-1"], text="The following table shows specifications."),
        ),
    ):
        rebuild_keyword_index(source_dir=corpus_dir, data_dir=data_dir)

    manifest = json.loads((data_dir / "active_index.json").read_text())
    index_dir = Path(manifest["index_dir"])
    store = json.loads((index_dir / "resource_store.json").read_text())

    table_entries = [e for e in store["entries"] if e["type"] == "table"]
    assert table_entries, "No table entries found in resource_store"
    assert table_entries[0]["related"], f"Table entry has no related: {table_entries[0]}"


def test_rebuild_pdf_uses_toc_chunker_without_chunk_size_fallback(tmp_path: Path) -> None:
    corpus_dir = tmp_path / "corpus"
    data_dir = tmp_path / "data"
    corpus_dir.mkdir(parents=True)
    (corpus_dir / "manual.pdf").write_bytes(b"%PDF-1.4")

    pdf_doc = _make_pdf_doc(
        [
            Element(
                element_id="el-0",
                element_type="text",
                text="short",
                heading_path="1 Intro",
                section_title="1 Intro",
                section_level=1,
                metadata={"page_number": 1},
            )
        ]
    )
    toc_chunks = _make_toc_chunks(pdf_doc, ["el-0"])

    with (
        patch("rag_mcp.indexing.rebuild.load_supported_documents", return_value=[pdf_doc]),
        patch("rag_mcp.indexing.rebuild.TocAwareChunker.chunk_document", return_value=toc_chunks) as mock_toc_chunk,
    ):
        rebuild_keyword_index(source_dir=corpus_dir, data_dir=data_dir, chunk_size=1, chunk_overlap=0)

    mock_toc_chunk.assert_called_once()

    manifest = json.loads((data_dir / "active_index.json").read_text())
    index_dir = Path(manifest["index_dir"])
    kw_store = json.loads((index_dir / "keyword_store.json").read_text())

    assert len(kw_store["entries"]) == 1
    assert kw_store["entries"][0]["text"] == "toc chunk text"


def test_rebuild_pdf_falls_back_when_toc_chunking_not_satisfied(tmp_path: Path) -> None:
    corpus_dir = tmp_path / "corpus"
    data_dir = tmp_path / "data"
    corpus_dir.mkdir(parents=True)
    (corpus_dir / "manual.pdf").write_bytes(b"%PDF-1.4")

    pdf_doc = SourceDocument(
        doc_id="pdf-doc",
        title="manual.pdf",
        relative_path="manual.pdf",
        file_type="pdf",
        text="",
        elements=[],
    )

    with (
        patch("rag_mcp.indexing.rebuild.load_supported_documents", return_value=[pdf_doc]),
        patch("rag_mcp.indexing.rebuild.TocAwareChunker.chunk_document", return_value=[]),
    ):
        result = rebuild_keyword_index(source_dir=corpus_dir, data_dir=data_dir)
    assert result["document_count"] == 1
    assert result["chunk_count"] == 0


def test_rebuild_accepts_non_pdf_with_fallback_chunking(tmp_path: Path) -> None:
    corpus_dir = tmp_path / "corpus"
    data_dir = tmp_path / "data"
    corpus_dir.mkdir(parents=True)

    md_doc = SourceDocument(
        doc_id="md-doc",
        title="doc.md",
        relative_path="doc.md",
        file_type="md",
        text="hello world this content is definitely long enough",
        elements=[
            Element(
                element_id="el-0",
                element_type="text",
                text="hello world this content is definitely long enough",
                heading_path="doc.md",
                section_title="doc.md",
                section_level=0,
            )
        ],
    )

    with patch("rag_mcp.indexing.rebuild.load_supported_documents", return_value=[md_doc]):
        result = rebuild_keyword_index(source_dir=corpus_dir, data_dir=data_dir)
    assert result["document_count"] == 1
    assert result["chunk_count"] >= 1
