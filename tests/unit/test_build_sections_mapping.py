from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from rag_mcp.ingestion.document_model import Document, Element
from rag_mcp.indexing.manifest import write_active_manifest_atomic
from rag_mcp.indexing.sections_mapping import build_sections_mapping


def _make_pdf_doc(relative_path: str) -> Document:
    return Document(
        doc_id="d1",
        title="manual.pdf",
        relative_path=relative_path,
        file_type="pdf",
        elements=[
            Element(
                element_id="e1",
                element_type="text",
                text="hello",
                heading_path="manual",
                section_title="manual",
                section_level=0,
            )
        ],
    )


def test_build_sections_mapping_from_toc(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    source_dir = tmp_path / "corpus"
    index_dir = data_dir / "indexes" / "idx-1"
    (source_dir / "manuals").mkdir(parents=True)
    index_dir.mkdir(parents=True)
    (source_dir / "manuals" / "doc.pdf").write_text("fake", encoding="utf-8")

    write_active_manifest_atomic(
        data_dir / "active_index.json",
        {
            "corpus_id": "c1",
            "index_dir": str(index_dir),
            "source_dir": str(source_dir),
            "indexed_at": 0,
            "document_count": 1,
            "chunk_count": 1,
            "embedding_model": None,
            "embedding_dimension": None,
        },
    )

    class _Node:
        def __init__(self, title: str) -> None:
            self.title = title
            self.heading_path = title
            self.level = 1
            self.page_start = 1
            self.page_end = 1

    with (
        patch(
            "rag_mcp.indexing.sections_mapping.load_supported_documents",
            return_value=[_make_pdf_doc("manuals/doc.pdf")],
        ),
        patch(
            "rag_mcp.indexing.sections_mapping._extract_toc_nodes",
            return_value=[_Node("1 前言"), _Node("1.1 安全")],
        ),
    ):
        output = build_sections_mapping(data_dir)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload == {"doc": ["1 前言", "1.1 安全"]}


def test_build_sections_mapping_fallback_to_elements(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    source_dir = tmp_path / "corpus"
    index_dir = data_dir / "indexes" / "idx-1"
    source_dir.mkdir(parents=True)
    index_dir.mkdir(parents=True)

    write_active_manifest_atomic(
        data_dir / "active_index.json",
        {
            "corpus_id": "c1",
            "index_dir": str(index_dir),
            "source_dir": str(source_dir),
            "indexed_at": 0,
            "document_count": 1,
            "chunk_count": 1,
            "embedding_model": None,
            "embedding_dimension": None,
        },
    )

    doc = Document(
        doc_id="d1",
        title="manual.pdf",
        relative_path="manual.pdf",
        file_type="pdf",
        elements=[
            Element(
                element_id="e1",
                element_type="text",
                text="a",
                heading_path="1 前言",
                section_title="1 前言",
                section_level=1,
            ),
            Element(
                element_id="e2",
                element_type="text",
                text="b",
                heading_path="1 前言 > 1.1 安全",
                section_title="1.1 安全",
                section_level=2,
            ),
            Element(
                element_id="e3",
                element_type="text",
                text="c",
                heading_path="1 前言 > 1.1 安全",
                section_title="1.1 安全",
                section_level=2,
            ),
        ],
    )

    with (
        patch(
            "rag_mcp.indexing.sections_mapping.load_supported_documents",
            return_value=[doc],
        ),
        patch("rag_mcp.indexing.sections_mapping._extract_toc_nodes", return_value=[]),
    ):
        output = build_sections_mapping(data_dir)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload == {"manual": ["1 前言", "1.1 安全"]}


def test_build_sections_mapping_with_direct_paths(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    source_dir = tmp_path / "corpus"
    index_dir = data_dir / "indexes" / "idx-1"
    (source_dir / "manuals").mkdir(parents=True)
    index_dir.mkdir(parents=True)
    (source_dir / "manuals" / "doc.pdf").write_text("fake", encoding="utf-8")

    class _Node:
        def __init__(self, title: str) -> None:
            self.title = title
            self.heading_path = title
            self.level = 1
            self.page_start = 1
            self.page_end = 1

    with (
        patch(
            "rag_mcp.indexing.sections_mapping.load_supported_documents",
            return_value=[_make_pdf_doc("manuals/doc.pdf")],
        ),
        patch(
            "rag_mcp.indexing.sections_mapping._extract_toc_nodes",
            return_value=[_Node("2 概述"), _Node("2.1 规格")],
        ),
    ):
        output = build_sections_mapping(
            data_dir=data_dir,
            source_dir=source_dir,
            index_dir=index_dir,
        )

    assert output == index_dir / "sections_mapping.json"
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload == {"doc": ["2 概述", "2.1 规格"]}


def test_build_sections_mapping_custom_output_path(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    source_dir = tmp_path / "corpus"
    index_dir = data_dir / "indexes" / "idx-1"
    custom_output = tmp_path / "custom" / "sections_mapping.json"
    (source_dir / "manuals").mkdir(parents=True)
    index_dir.mkdir(parents=True)
    (source_dir / "manuals" / "doc.pdf").write_text("fake", encoding="utf-8")

    class _Node:
        def __init__(self, title: str) -> None:
            self.title = title
            self.heading_path = title
            self.level = 1
            self.page_start = 1
            self.page_end = 1

    with (
        patch(
            "rag_mcp.indexing.sections_mapping.load_supported_documents",
            return_value=[_make_pdf_doc("manuals/doc.pdf")],
        ),
        patch(
            "rag_mcp.indexing.sections_mapping._extract_toc_nodes",
            return_value=[_Node("3 安装")],
        ),
    ):
        output = build_sections_mapping(
            data_dir=data_dir,
            output_path=custom_output,
            source_dir=source_dir,
            index_dir=index_dir,
        )

    assert output == custom_output
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload == {"doc": ["3 安装"]}
