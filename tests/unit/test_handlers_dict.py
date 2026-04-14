from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import json

from rag_mcp.transport.handlers import ToolHandlers


def _make_handlers(tmp_path: Path) -> ToolHandlers:
    return ToolHandlers(data_dir=tmp_path)


def test_rebuild_index_returns_dict(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "doc.md").write_text("# A\n\ncontent", encoding="utf-8")
    h = _make_handlers(tmp_path)
    with patch("rag_mcp.transport.handlers.rebuild_keyword_index", return_value={"corpus_id": "abc", "chunk_count": 1, "document_count": 1, "indexed_at": 0, "index_dir": str(tmp_path), "embedding_model": "", "embedding_dimension": 0}):
        result = h.rebuild_index(str(corpus))
    assert isinstance(result, dict)
    assert "corpus_id" in result or "error" in result


def test_index_status_returns_dict(tmp_path: Path) -> None:
    h = _make_handlers(tmp_path)
    result = h.index_status()
    assert isinstance(result, dict)
    assert "has_active_index" in result


def test_index_status_contains_filenames(tmp_path: Path) -> None:
    _write_active_keyword_store(tmp_path)
    h = _make_handlers(tmp_path)
    result = h.index_status()
    assert isinstance(result, dict)
    assert result["has_active_index"] is True
    assert "filenames" in result
    assert "doc" in result["filenames"]


def test_search_returns_dict(tmp_path: Path) -> None:
    h = _make_handlers(tmp_path)
    mock_retrieval = MagicMock()
    mock_retrieval.search.return_value = {
        "mode": "keyword", "result_count": 1,
        "results": [{"uri": "rag://corpus/c/d#text-0", "text": "hello", "title": "t", "score": 1.0, "metadata": {}}]
    }
    h.retrieval = mock_retrieval
    result = h.search(query="hello", top_k=3)
    assert isinstance(result, dict)
    assert "results" in result or "error" in result


def test_read_resource_returns_dict(tmp_path: Path) -> None:
    h = _make_handlers(tmp_path)
    mock_resources = MagicMock()
    mock_resources.read.return_value = {
        "uri": "rag://corpus/c/d#text-0",
        "type": "text",
        "text": "hello",
        "metadata": {}
    }
    h.resources = mock_resources
    result = h.read_resource(uri="rag://corpus/c/d#text-0")
    assert isinstance(result, dict)
    assert "uri" in result or "error" in result


def test_read_resources_returns_dict(tmp_path: Path) -> None:
    h = _make_handlers(tmp_path)
    mock_resources = MagicMock()
    mock_resources.read.return_value = {
        "uri": "rag://corpus/c/d#text-0",
        "type": "text",
        "text": "hello",
        "metadata": {},
    }
    h.resources = mock_resources
    result = h.read_resources(uris=["rag://corpus/c/d#text-0"])
    assert isinstance(result, dict)
    assert result["count"] == 1
    assert result["success_count"] == 1
    assert result["error_count"] == 0


def _write_active_keyword_store(tmp_path: Path) -> None:
    index_dir = tmp_path / "indexes" / "idx-test"
    index_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "active_index.json").write_text(
        json.dumps(
            {
                "corpus_id": "c1",
                "index_dir": str(index_dir),
                "source_dir": str(tmp_path / "corpus"),
                "indexed_at": 0,
                "document_count": 1,
                "chunk_count": 2,
            }
        ),
        encoding="utf-8",
    )
    payload = {
        "corpus_id": "c1",
        "entries": [
            {
                "text": "A",
                "title": "manual.pdf",
                "uri": "rag://corpus/c1/d1#text-0",
                "metadata": {
                    "relative_path": "manuals/doc.pdf",
                    "file_type": "pdf",
                    "chunk_index": 0,
                    "heading_path": "1 前言",
                    "section_title": "1 前言",
                    "section_level": 1,
                },
                "related_resource_uris": [],
            },
            {
                "text": "B",
                "title": "manual.pdf",
                "uri": "rag://corpus/c1/d1#text-1",
                "metadata": {
                    "relative_path": "manuals/doc.pdf",
                    "file_type": "pdf",
                    "chunk_index": 1,
                    "heading_path": "1 前言 > 1.1 安全",
                    "section_title": "1.1 安全",
                    "section_level": 2,
                },
                "related_resource_uris": ["rag://corpus/c1/d1#image-0"],
            },
        ],
    }
    (index_dir / "keyword_store.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (index_dir / "sections_mapping.json").write_text(
        json.dumps({"doc": ["1 前言", "1.1 安全"]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )



def test_list_filenames_returns_dict(tmp_path: Path) -> None:
    _write_active_keyword_store(tmp_path)
    h = _make_handlers(tmp_path)
    result = h.list_filenames()
    assert isinstance(result, dict)
    assert result["count"] == 1
    assert result["filenames"][0]["filename"] == "doc"


def test_list_sections_returns_dict(tmp_path: Path) -> None:
    _write_active_keyword_store(tmp_path)
    h = _make_handlers(tmp_path)
    result = h.list_sections("doc")
    assert isinstance(result, dict)
    assert "doc" in result
    assert result["doc"] == ["1 前言", "1.1 安全"]


def test_list_sections_returns_error_when_mapping_missing(tmp_path: Path) -> None:
    _write_active_keyword_store(tmp_path)
    index_dir = tmp_path / "indexes" / "idx-test"
    (index_dir / "sections_mapping.json").unlink()
    h = _make_handlers(tmp_path)
    result = h.list_sections("doc")
    assert isinstance(result, dict)
    assert result["error"] == "RESOURCE_NOT_FOUND"
def test_list_sections_returns_error_when_filename_missing(tmp_path: Path) -> None:
    _write_active_keyword_store(tmp_path)
    h = _make_handlers(tmp_path)
    result = h.list_sections("missing")
    assert isinstance(result, dict)
    assert result["error"] == "invalid_filename"


def test_section_retrieval_returns_dict(tmp_path: Path) -> None:
    _write_active_keyword_store(tmp_path)
    h = _make_handlers(tmp_path)
    result = h.section_retrieval(
        section_title=["1.1 安全"],
        filename="doc",
    )
    assert isinstance(result, dict)
    assert result["result_count"] == 1
    assert result["results"][0]["title"] == "1.1 安全"
    assert result["results"][0]["filename"] == "doc"


def test_section_retrieval_invalid_title_returns_error(tmp_path: Path) -> None:
    _write_active_keyword_store(tmp_path)
    h = _make_handlers(tmp_path)
    result = h.section_retrieval(
        section_title=["不存在章节"],
        filename="doc",
    )
    assert isinstance(result, dict)
    assert result["error"] == "invalid_title"
