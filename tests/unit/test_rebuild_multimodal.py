from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from rag_mcp.indexing.rebuild import rebuild_keyword_index


def _write_corpus(d: Path) -> None:
    d.mkdir(parents=True, exist_ok=True)
    (d / "doc.md").write_text("# Chapter 1\n\n## Section\n\nhello world text", encoding="utf-8")
    (d / "notes.txt").write_text("plain text notes", encoding="utf-8")


def test_rebuild_creates_resource_store_json(tmp_path: Path) -> None:
    corpus_dir = tmp_path / "corpus"
    data_dir = tmp_path / "data"
    _write_corpus(corpus_dir)

    rebuild_keyword_index(source_dir=corpus_dir, data_dir=data_dir)

    manifest = json.loads((data_dir / "active_index.json").read_text())
    index_dir = Path(manifest["index_dir"])
    assert (index_dir / "resource_store.json").exists()


def test_rebuild_resource_store_has_text_entries(tmp_path: Path) -> None:
    corpus_dir = tmp_path / "corpus"
    data_dir = tmp_path / "data"
    _write_corpus(corpus_dir)

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
    _write_corpus(corpus_dir)

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
    corpus_dir.mkdir(parents=True, exist_ok=True)
    (corpus_dir / "doc.md").write_text("# A\n\ncontent", encoding="utf-8")

    mock_vlm = MagicMock()
    rebuild_keyword_index(source_dir=corpus_dir, data_dir=data_dir, vlm_client=mock_vlm)

    # vlm_client.describe_image should not be called (no images in md file)
    mock_vlm.describe_image.assert_not_called()


def test_rebuild_table_entry_has_related_chunk_uri(tmp_path: Path) -> None:
    from unittest.mock import patch

    from rag_mcp.ingestion.document_model import Element
    from rag_mcp.models import SourceDocument

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
        title="doc.md",
        relative_path="doc.md",
        file_type="md",
        text="The following table shows specifications.",
        elements=elements,
    )

    with patch("rag_mcp.indexing.rebuild.load_supported_documents", return_value=[fake_doc]):
        rebuild_keyword_index(source_dir=corpus_dir, data_dir=data_dir)

    manifest = json.loads((data_dir / "active_index.json").read_text())
    index_dir = Path(manifest["index_dir"])
    store = json.loads((index_dir / "resource_store.json").read_text())

    table_entries = [e for e in store["entries"] if e["type"] == "table"]
    assert table_entries, "No table entries found in resource_store"
    assert table_entries[0]["related"], f"Table entry has no related: {table_entries[0]}"
