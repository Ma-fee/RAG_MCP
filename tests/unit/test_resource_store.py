from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from rag_mcp.ingestion.document_model import Document, Element
from rag_mcp.indexing.resource_store import ResourceStore


def make_doc(elements):
    return Document(
        doc_id="doc1",
        title="test",
        relative_path="test.pdf",
        file_type="pdf",
        elements=elements,
    )


def make_text_el(i, text="hello"):
    return Element(
        element_id=f"el-{i}",
        element_type="text",
        text=text,
        heading_path="Chapter 1",
        section_title="Intro",
        section_level=1,
    )


def make_image_el(i, image_path):
    return Element(
        element_id=f"el-img-{i}",
        element_type="image",
        text="",
        heading_path="Chapter 1",
        section_title="Intro",
        section_level=1,
        metadata={"image_path": str(image_path), "caption": f"图{i}", "page_number": 1},
    )


def make_table_el(i):
    return Element(
        element_id=f"el-tbl-{i}",
        element_type="table",
        text="",
        heading_path="Chapter 1",
        section_title="Intro",
        section_level=1,
        metadata={"markdown": "| a | b |\n|---|---|\n| 1 | 2 |", "caption": f"表{i}", "page_number": 2},
    )


def test_build_creates_resource_store_json(tmp_path):
    doc = make_doc([make_text_el(0)])
    store = ResourceStore(index_dir=tmp_path, corpus_id="c1", vlm_client=None)
    store.build(doc)
    assert (tmp_path / "resource_store.json").exists()


def test_text_uri_format(tmp_path):
    doc = make_doc([make_text_el(0)])
    store = ResourceStore(index_dir=tmp_path, corpus_id="c1", vlm_client=None)
    entries = store.build(doc)
    assert entries[0]["uri"] == "rag://corpus/c1/doc1#text-0"
    assert entries[0]["type"] == "text"


def test_image_uri_format(tmp_path):
    img = tmp_path / "img.png"
    img.write_bytes(b"fake")
    doc = make_doc([make_image_el(0, img)])
    mock_vlm = MagicMock()
    mock_vlm.describe_image.return_value = "液压图"
    store = ResourceStore(index_dir=tmp_path, corpus_id="c1", vlm_client=mock_vlm)
    entries = store.build(doc)
    assert entries[0]["uri"] == "rag://corpus/c1/doc1#image-0"
    assert entries[0]["type"] == "image"
    assert entries[0]["vlm_description"] == "液压图"


def test_table_uri_format(tmp_path):
    doc = make_doc([make_table_el(0)])
    store = ResourceStore(index_dir=tmp_path, corpus_id="c1", vlm_client=None)
    entries = store.build(doc)
    assert entries[0]["uri"] == "rag://corpus/c1/doc1#table-0"
    assert entries[0]["type"] == "table"
    assert "markdown" in entries[0]


def test_get_returns_entry_by_uri(tmp_path):
    doc = make_doc([make_text_el(0, "some text"), make_table_el(0)])
    store = ResourceStore(index_dir=tmp_path, corpus_id="c1", vlm_client=None)
    store.build(doc)
    entry = store.get("rag://corpus/c1/doc1#table-0")
    assert entry is not None
    assert entry["type"] == "table"


def test_get_returns_none_for_missing_uri(tmp_path):
    doc = make_doc([make_text_el(0)])
    store = ResourceStore(index_dir=tmp_path, corpus_id="c1", vlm_client=None)
    store.build(doc)
    assert store.get("rag://corpus/c1/doc1#image-99") is None


def test_image_vlm_skipped_when_no_client(tmp_path):
    img = tmp_path / "img.png"
    img.write_bytes(b"fake")
    doc = make_doc([make_image_el(0, img)])
    store = ResourceStore(index_dir=tmp_path, corpus_id="c1", vlm_client=None)
    entries = store.build(doc)
    assert entries[0]["vlm_description"] == ""


def test_build_persists_all_entry_types(tmp_path):
    img = tmp_path / "img.png"
    img.write_bytes(b"fake")
    elements = [make_text_el(0), make_image_el(0, img), make_table_el(0)]
    doc = make_doc(elements)
    store = ResourceStore(index_dir=tmp_path, corpus_id="c1", vlm_client=None)
    entries = store.build(doc)
    data = json.loads((tmp_path / "resource_store.json").read_text(encoding="utf-8"))
    assert len(data["entries"]) == 3
    types = {e["type"] for e in data["entries"]}
    assert types == {"text", "image", "table"}


def test_multiple_docs_build_separate_entries(tmp_path):
    doc1 = Document(
        doc_id="docA",
        title="A",
        relative_path="a.pdf",
        file_type="pdf",
        elements=[make_text_el(0, "doc A text")],
    )
    store = ResourceStore(index_dir=tmp_path, corpus_id="corp", vlm_client=None)
    entries = store.build(doc1)
    assert entries[0]["uri"] == "rag://corpus/corp/docA#text-0"
    assert entries[0]["doc_id"] == "docA"


def test_text_entry_has_required_fields(tmp_path):
    doc = make_doc([make_text_el(0, "content text")])
    store = ResourceStore(index_dir=tmp_path, corpus_id="c1", vlm_client=None)
    entries = store.build(doc)
    e = entries[0]
    assert e["uri"]
    assert e["type"] == "text"
    assert e["text"] == "content text"
    assert e["heading_path"] == "Chapter 1"
    assert e["section_title"] == "Intro"
    assert e["doc_id"] == "doc1"
    assert "related" in e


def test_image_entry_has_required_fields(tmp_path):
    img = tmp_path / "img.png"
    img.write_bytes(b"fake")
    doc = make_doc([make_image_el(0, img)])
    store = ResourceStore(index_dir=tmp_path, corpus_id="c1", vlm_client=None)
    entries = store.build(doc)
    e = entries[0]
    assert e["uri"]
    assert e["type"] == "image"
    assert "image_path" in e
    assert "caption" in e
    assert "related" in e


def test_table_entry_has_required_fields(tmp_path):
    doc = make_doc([make_table_el(0)])
    store = ResourceStore(index_dir=tmp_path, corpus_id="c1", vlm_client=None)
    entries = store.build(doc)
    e = entries[0]
    assert e["uri"]
    assert e["type"] == "table"
    assert "markdown" in e
    assert "caption" in e
    assert "related" in e
