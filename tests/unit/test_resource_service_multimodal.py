from __future__ import annotations

import json
from pathlib import Path

import pytest

from rag_mcp.errors import ErrorCode, ServiceException
from rag_mcp.resources.service import ResourceService


def _write_manifest(data_dir: Path, index_dir: Path, corpus_id: str) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "active_index.json").write_text(
        json.dumps({"corpus_id": corpus_id, "index_dir": str(index_dir)}),
        encoding="utf-8",
    )


def _write_resource_store(index_dir: Path, entries: list[dict]) -> None:
    index_dir.mkdir(parents=True, exist_ok=True)
    (index_dir / "resource_store.json").write_text(
        json.dumps({"entries": entries}, ensure_ascii=False),
        encoding="utf-8",
    )


def _write_keyword_store(index_dir: Path, corpus_id: str) -> None:
    index_dir.mkdir(parents=True, exist_ok=True)
    (index_dir / "keyword_store.json").write_text(
        json.dumps({"corpus_id": corpus_id, "entries": []}),
        encoding="utf-8",
    )


def test_read_image_uri_returns_vlm_description(tmp_path: Path) -> None:
    index_dir = tmp_path / "idx"
    corpus_id = "abc123"
    doc_id = "doc456"
    uri = f"rag://corpus/{corpus_id}/{doc_id}#image-0"

    _write_manifest(tmp_path, index_dir, corpus_id)
    _write_keyword_store(index_dir, corpus_id)
    _write_resource_store(index_dir, [
        {
            "uri": uri,
            "type": "image",
            "doc_id": doc_id,
            "element_id": "el-img-0",
            "image_path": "/some/path/image-0.png",
            "page_number": 1,
            "vlm_description": "液压泵结构图",
            "related": [],
        }
    ])

    svc = ResourceService(data_dir=tmp_path)
    result = svc.read(uri)

    assert result["uri"] == uri
    assert result["type"] == "image"
    assert result["vlm_description"] == "液压泵结构图"


def test_read_table_uri_returns_markdown(tmp_path: Path) -> None:
    index_dir = tmp_path / "idx"
    corpus_id = "abc123"
    doc_id = "doc456"
    uri = f"rag://corpus/{corpus_id}/{doc_id}#table-0"

    _write_manifest(tmp_path, index_dir, corpus_id)
    _write_keyword_store(index_dir, corpus_id)
    _write_resource_store(index_dir, [
        {
            "uri": uri,
            "type": "table",
            "doc_id": doc_id,
            "element_id": "el-tbl-0",
            "markdown": "| a | b |\n|---|---|\n| 1 | 2 |",
            "data_json": "",
            "page_number": 2,
            "related": [],
        }
    ])

    svc = ResourceService(data_dir=tmp_path)
    result = svc.read(uri)

    assert result["uri"] == uri
    assert result["type"] == "table"
    assert "| a | b |" in result["markdown"]


def test_read_text_uri_still_works(tmp_path: Path) -> None:
    index_dir = tmp_path / "idx"
    corpus_id = "abc123"
    doc_id = "doc456"
    uri = f"rag://corpus/{corpus_id}/{doc_id}#text-0"

    _write_manifest(tmp_path, index_dir, corpus_id)
    _write_resource_store(index_dir, [])
    index_dir.mkdir(parents=True, exist_ok=True)
    (index_dir / "keyword_store.json").write_text(
        json.dumps({"corpus_id": corpus_id, "entries": [
            {
                "uri": uri,
                "text": "hello world",
                "title": "doc",
                "metadata": {"doc_id": doc_id, "chunk_index": 0,
                             "corpus_id": corpus_id, "file_type": "md",
                             "title": "doc", "section_title": "sec",
                             "heading_path": "sec", "section_level": 1,
                             "relative_path": "doc.md", "chunk_length": 11},
            }
        ]}),
        encoding="utf-8",
    )

    svc = ResourceService(data_dir=tmp_path)
    result = svc.read(uri)

    assert result["uri"] == uri
    assert result["text"] == "hello world"


def test_read_image_uri_not_found_raises(tmp_path: Path) -> None:
    index_dir = tmp_path / "idx"
    corpus_id = "abc123"
    doc_id = "doc456"
    uri = f"rag://corpus/{corpus_id}/{doc_id}#image-99"

    _write_manifest(tmp_path, index_dir, corpus_id)
    _write_keyword_store(index_dir, corpus_id)
    _write_resource_store(index_dir, [])

    svc = ResourceService(data_dir=tmp_path)
    with pytest.raises(ServiceException) as exc:
        svc.read(uri)
    assert exc.value.error.code == ErrorCode.RESOURCE_NOT_FOUND
