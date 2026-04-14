from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _make_service(tmp_path: Path, reranker=None, rerank_top_k_candidates: int = 20):
    from rag_mcp.retrieval.service import RetrievalService
    return RetrievalService(
        data_dir=tmp_path,
        embedding_provider=MagicMock(),
        reranker=reranker,
        rerank_top_k_candidates=rerank_top_k_candidates,
    )


def _fake_manifest(index_dir: str) -> dict:
    return {
        "corpus_id": "abc",
        "index_dir": index_dir,
        "embedding_model": "test",
        "embedding_dimension": 4,
        "document_count": 1,
        "chunk_count": 3,
        "indexed_at": 0,
    }


def _make_hits(n: int) -> list[dict]:
    return [
        {"uri": f"rag://c/d#text-{i}", "text": f"text {i}", "title": "t", "score": float(n - i), "metadata": {}}
        for i in range(n)
    ]


def _keyword_result(hits: list[dict]) -> dict:
    return {"results": hits, "query": "q", "mode": "keyword", "top_k": len(hits), "result_count": len(hits)}


# ── mode label ────────────────────────────────────────────────────────────────

def test_rerank_returns_mode_rerank(tmp_path: Path) -> None:
    mock_reranker = MagicMock()
    mock_reranker.rerank.return_value = _make_hits(3)
    svc = _make_service(tmp_path, reranker=mock_reranker)
    with (
        patch("rag_mcp.retrieval.service.read_active_manifest", return_value=_fake_manifest(str(tmp_path))),
        patch.object(svc, "_search_keyword", return_value=_keyword_result(_make_hits(3))),
        patch.object(svc, "_search_vector", return_value={"results": [], "result_count": 0}),
        patch.object(svc, "_split_query_intent", return_value={"keyword_query": "qk", "vector_query": "qv"}),
    ):
        result = svc.search(query="q", top_k=3)
    assert result["mode"] == "hybrid_rerank"


# ── top_k truncation ──────────────────────────────────────────────────────────

def test_rerank_respects_top_k(tmp_path: Path) -> None:
    hits = _make_hits(6)
    mock_reranker = MagicMock()
    mock_reranker.rerank.return_value = hits  # returns all 6
    svc = _make_service(tmp_path, reranker=mock_reranker)
    with (
        patch("rag_mcp.retrieval.service.read_active_manifest", return_value=_fake_manifest(str(tmp_path))),
        patch.object(svc, "_search_keyword", return_value=_keyword_result(hits)),
        patch.object(svc, "_search_vector", return_value={"results": [], "result_count": 0}),
        patch.object(svc, "_split_query_intent", return_value={"keyword_query": "qk", "vector_query": "qv"}),
    ):
        result = svc.search(query="q", top_k=3)
    assert len(result["results"]) == 3


# ── ordering ──────────────────────────────────────────────────────────────────

def test_rerank_sorts_by_reranker_score(tmp_path: Path) -> None:
    """Reranker reverses original order; service should honour it."""
    original = _make_hits(4)  # scores 4,3,2,1
    reversed_hits = list(reversed(original))  # reranker returns 1,2,3,4
    mock_reranker = MagicMock()
    mock_reranker.rerank.return_value = reversed_hits
    svc = _make_service(tmp_path, reranker=mock_reranker)
    with (
        patch("rag_mcp.retrieval.service.read_active_manifest", return_value=_fake_manifest(str(tmp_path))),
        patch.object(svc, "_search_keyword", return_value=_keyword_result(original)),
        patch.object(svc, "_search_vector", return_value={"results": [], "result_count": 0}),
        patch.object(svc, "_split_query_intent", return_value={"keyword_query": "qk", "vector_query": "qv"}),
    ):
        result = svc.search(query="q", top_k=4)
    uris = [r["uri"] for r in result["results"]]
    assert uris == [h["uri"] for h in reversed_hits]


# ── no reranker ───────────────────────────────────────────────────────────────

def test_rerank_falls_back_to_keyword_when_no_reranker(tmp_path: Path) -> None:
    hits = _make_hits(5)
    svc = _make_service(tmp_path, reranker=None)
    with patch.object(svc, "_search_keyword", return_value=_keyword_result(hits)):
        with (
            patch.object(svc, "_search_vector", return_value={"results": [], "result_count": 0}),
            patch.object(svc, "_split_query_intent", return_value={"keyword_query": "qk", "vector_query": "qv"}),
        ):
            result = svc.search(query="q", top_k=3)
    assert result["mode"] == "hybrid_rerank"
    assert len(result["results"]) == 3
    assert result["results"][0]["uri"] == hits[0]["uri"]


# ── ApiReranker ──────────────────────────────────────────────────────────────

def test_api_reranker_scores_and_sorts() -> None:
    from rag_mcp.retrieval.reranker import ApiReranker
    candidates = [
        {"uri": "u1", "text": "low relevance", "score": 1.0},
        {"uri": "u2", "text": "high relevance", "score": 0.5},
    ]
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "results": [{"index": 1, "relevance_score": 0.9}, {"index": 0, "relevance_score": 0.2}]
    }
    reranker = ApiReranker(api_key="k", base_url="http://x", model="m")
    with patch("rag_mcp.retrieval.reranker.httpx.post", return_value=mock_resp):
        result = reranker.rerank(query="q", candidates=candidates)
    assert result[0]["uri"] == "u2"
    assert result[0]["score"] == pytest.approx(0.9)


def test_api_reranker_empty_candidates() -> None:
    from rag_mcp.retrieval.reranker import ApiReranker
    reranker = ApiReranker(api_key="k", base_url="http://x", model="m")
    assert reranker.rerank(query="q", candidates=[]) == []


# ── build_reranker factory ────────────────────────────────────────────────────

def _make_cfg(**overrides):
    from rag_mcp.config import AppConfig
    defaults = dict(
        data_dir="/tmp",
        http_host="127.0.0.1",
        http_port=8787,
        embedding_api_key="",
        embedding_base_url="",
        embedding_model="",
        embedding_dimension=None,
        embedding_timeout_seconds=30,
        default_top_k=5,
        keyword_top_k=8,
        chunk_size=800,
        chunk_overlap=120,
        multimodal_api_key="",
        multimodal_base_url="http://api",
        multimodal_model="model",
        mcp_transport="stdio",
        rerank_api_key="",
        rerank_base_url="https://api.siliconflow.cn/v1",
        rerank_model="Qwen/Qwen3-Reranker-0.6B",
        rerank_timeout_seconds=30,
        rerank_top_k_candidates=20,
    )
    defaults.update(overrides)
    from pathlib import Path
    defaults["data_dir"] = Path(defaults["data_dir"])
    return AppConfig(**defaults)


def test_build_reranker_returns_none_when_no_api_key() -> None:
    from rag_mcp.retrieval.reranker import build_reranker
    assert build_reranker(_make_cfg(rerank_api_key="")) is None


def test_build_reranker_returns_api_reranker_with_key() -> None:
    from rag_mcp.retrieval.reranker import ApiReranker, build_reranker
    result = build_reranker(_make_cfg(rerank_api_key="sk-test"))
    assert isinstance(result, ApiReranker)
    assert result.api_key == "sk-test"
    assert result.model == "Qwen/Qwen3-Reranker-0.6B"
