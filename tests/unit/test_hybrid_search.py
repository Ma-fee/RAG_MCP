from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _make_service(tmp_path: Path):
    from rag_mcp.retrieval.service import RetrievalService
    return RetrievalService(data_dir=tmp_path, embedding_provider=MagicMock())


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


def test_hybrid_returns_mode_hybrid(tmp_path: Path) -> None:
    svc = _make_service(tmp_path)
    with (
        patch("rag_mcp.retrieval.service.read_active_manifest", return_value=_fake_manifest(str(tmp_path))),
        patch.object(svc, "_search_keyword", return_value={"results": [], "query": "q", "mode": "keyword", "top_k": 5, "result_count": 0}),
        patch.object(svc, "_search_vector", return_value={"results": [], "query": "q", "mode": "vector", "top_k": 5, "result_count": 0}),
    ):
        result = svc.search(query="q", mode="hybrid", top_k=5)
    assert result["mode"] == "hybrid"


def test_hybrid_deduplicates_results(tmp_path: Path) -> None:
    """Same URI appearing in both keyword and vector results should appear once."""
    svc = _make_service(tmp_path)
    shared = {"uri": "rag://c/d#text-0", "text": "hello", "title": "t", "score": 1.0, "metadata": {}}
    only_kw = {"uri": "rag://c/d#text-1", "text": "world", "title": "t", "score": 0.5, "metadata": {}}
    only_vec = {"uri": "rag://c/d#text-2", "text": "foo", "title": "t", "score": 0.8, "metadata": {}}

    with (
        patch("rag_mcp.retrieval.service.read_active_manifest", return_value=_fake_manifest(str(tmp_path))),
        patch.object(svc, "_search_keyword", return_value={"results": [shared, only_kw], "query": "q", "mode": "keyword", "top_k": 5, "result_count": 2}),
        patch.object(svc, "_search_vector", return_value={"results": [shared, only_vec], "query": "q", "mode": "vector", "top_k": 5, "result_count": 2}),
    ):
        result = svc.search(query="q", mode="hybrid", top_k=10)

    uris = [r["uri"] for r in result["results"]]
    assert len(uris) == len(set(uris)), "Duplicate URIs in hybrid results"
    assert len(uris) == 3


def test_hybrid_rrf_ranks_double_hit_higher(tmp_path: Path) -> None:
    """A URI that appears in both keyword and vector results should rank above a URI in only one."""
    svc = _make_service(tmp_path)
    double_hit = {"uri": "rag://c/d#text-0", "text": "both", "title": "t", "score": 0.5, "metadata": {}}
    single_hit = {"uri": "rag://c/d#text-1", "text": "only kw", "title": "t", "score": 1.0, "metadata": {}}

    with (
        patch("rag_mcp.retrieval.service.read_active_manifest", return_value=_fake_manifest(str(tmp_path))),
        patch.object(svc, "_search_keyword", return_value={"results": [single_hit, double_hit], "query": "q", "mode": "keyword", "top_k": 5, "result_count": 2}),
        patch.object(svc, "_search_vector", return_value={"results": [double_hit], "query": "q", "mode": "vector", "top_k": 5, "result_count": 1}),
    ):
        result = svc.search(query="q", mode="hybrid", top_k=10)

    uris = [r["uri"] for r in result["results"]]
    assert uris[0] == "rag://c/d#text-0", f"Expected double-hit first, got: {uris}"


def test_hybrid_respects_top_k(tmp_path: Path) -> None:
    svc = _make_service(tmp_path)
    hits = [{"uri": f"rag://c/d#text-{i}", "text": f"t{i}", "title": "t", "score": 1.0, "metadata": {}} for i in range(6)]

    with (
        patch("rag_mcp.retrieval.service.read_active_manifest", return_value=_fake_manifest(str(tmp_path))),
        patch.object(svc, "_search_keyword", return_value={"results": hits[:6], "query": "q", "mode": "keyword", "top_k": 6, "result_count": 6}),
        patch.object(svc, "_search_vector", return_value={"results": hits[:6], "query": "q", "mode": "vector", "top_k": 6, "result_count": 6}),
    ):
        result = svc.search(query="q", mode="hybrid", top_k=3)

    assert result["result_count"] == 3
    assert len(result["results"]) == 3
