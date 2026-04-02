from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch


def _make_service(tmp_path: Path, reranker=None):
    from rag_mcp.retrieval.service import RetrievalService

    return RetrievalService(
        data_dir=tmp_path,
        embedding_provider=MagicMock(),
        reranker=reranker,
        rerank_top_k_candidates=20,
    )


def _make_hits(n: int) -> list[dict]:
    return [
        {
            "uri": f"rag://c/d#text-{i}",
            "text": f"text {i}",
            "title": "t",
            "score": float(n - i),
            "metadata": {},
        }
        for i in range(n)
    ]


def _keyword_result(hits: list[dict]) -> dict:
    return {
        "results": hits,
        "query": "q",
        "mode": "keyword",
        "top_k": len(hits),
        "result_count": len(hits),
    }


def test_search_ignores_mode_and_uses_rerank(tmp_path: Path) -> None:
    reranker = MagicMock()
    reranker.rerank.return_value = _make_hits(2)
    svc = _make_service(tmp_path, reranker=reranker)
    with patch.object(svc, "_search_keyword", return_value=_keyword_result(_make_hits(2))):
        result = svc.search(query="q", mode="hybrid", top_k=2)
    assert result["mode"] == "rerank"
    reranker.rerank.assert_called_once()


def test_search_without_reranker_falls_back_to_keyword_order(tmp_path: Path) -> None:
    svc = _make_service(tmp_path, reranker=None)
    hits = _make_hits(4)
    with patch.object(svc, "_search_keyword", return_value=_keyword_result(hits)):
        result = svc.search(query="q", mode="vector", top_k=3)
    assert len(result["results"]) == 3
    assert result["results"][0]["uri"] == hits[0]["uri"]
