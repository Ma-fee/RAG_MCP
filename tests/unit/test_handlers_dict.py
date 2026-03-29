from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

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


def test_search_returns_dict(tmp_path: Path) -> None:
    h = _make_handlers(tmp_path)
    mock_retrieval = MagicMock()
    mock_retrieval.search.return_value = {
        "mode": "keyword", "result_count": 1,
        "results": [{"uri": "rag://corpus/c/d#text-0", "text": "hello", "title": "t", "score": 1.0, "metadata": {}}]
    }
    h.retrieval = mock_retrieval
    result = h.search(query="hello", mode="keyword", top_k=3)
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
