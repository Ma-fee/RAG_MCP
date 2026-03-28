from __future__ import annotations

from pathlib import Path

import pytest
import xml.etree.ElementTree as ET

from rag_mcp.errors import ErrorCode, ServiceException
from rag_mcp.indexing.rebuild import rebuild_keyword_index
from rag_mcp.resources.service import ResourceService
from rag_mcp.retrieval.service import RetrievalService
from rag_mcp.transport.stdio_server import StdioServer


def _write_corpus(corpus_dir: Path) -> None:
    corpus_dir.mkdir(parents=True, exist_ok=True)
    (corpus_dir / "README.md").write_text(
        "# RFC\n\n## Design\n\nkeyword retrieval over rag uri resources", encoding="utf-8"
    )
    (corpus_dir / "notes.txt").write_text(
        "stdio mcp should return structured keyword hits", encoding="utf-8"
    )


def test_keyword_search_and_resource_readback_flow(tmp_path: Path) -> None:
    corpus_dir = tmp_path / "corpus"
    data_dir = tmp_path / "data"
    _write_corpus(corpus_dir)

    rebuild_keyword_index(corpus_dir, data_dir, chunk_size=64, chunk_overlap=8)

    retrieval = RetrievalService(data_dir=data_dir)
    resource_service = ResourceService(data_dir=data_dir)

    search_payload = retrieval.search(
        query="keyword retrieval",
        mode="keyword",
        top_k=5,
    )

    assert search_payload["mode"] == "keyword"
    assert search_payload["result_count"] >= 1
    result = search_payload["results"][0]
    assert {"text", "title", "uri", "score", "metadata"} <= result.keys()
    assert result["uri"].startswith("rag://corpus/")

    resource_payload = resource_service.read(result["uri"])
    assert resource_payload["uri"] == result["uri"]
    assert resource_payload["text"] == result["text"]
    assert resource_payload["metadata"]["doc_id"] == result["metadata"]["doc_id"]


def test_vector_mode_reports_not_implemented(tmp_path: Path) -> None:
    corpus_dir = tmp_path / "corpus"
    data_dir = tmp_path / "data"
    _write_corpus(corpus_dir)
    rebuild_keyword_index(corpus_dir, data_dir, chunk_size=64, chunk_overlap=8)
    retrieval = RetrievalService(data_dir=data_dir)

    with pytest.raises(ServiceException) as exc:
        retrieval.search(query="anything", mode="vector", top_k=5)

    assert exc.value.error.code == ErrorCode.SEARCH_MODE_NOT_IMPLEMENTED


def test_stdio_server_returns_xml_for_tools_and_errors(tmp_path: Path) -> None:
    corpus_dir = tmp_path / "corpus"
    data_dir = tmp_path / "data"
    _write_corpus(corpus_dir)
    server = StdioServer(data_dir=data_dir)

    rebuild_xml = server.rag_rebuild_index(str(corpus_dir))
    rebuild_root = ET.fromstring(rebuild_xml)
    assert rebuild_root.findtext("status") == "ok"
    assert rebuild_root.findtext("data/index-rebuild-result/corpus_id")

    status_xml = server.rag_index_status()
    status_root = ET.fromstring(status_xml)
    assert status_root.findtext("status") == "ok"
    assert status_root.findtext("data/index-status/has_active_index") == "true"

    search_xml = server.rag_search(query="keyword retrieval", mode="keyword", top_k=3)
    search_root = ET.fromstring(search_xml)
    assert search_root.findtext("status") == "ok"
    assert search_root.findtext("data/search-results/mode") == "keyword"
    assert int(search_root.findtext("data/search-results/result_count") or "0") >= 1

    not_impl_xml = server.rag_search(query="x", mode="vector", top_k=3)
    not_impl_root = ET.fromstring(not_impl_xml)
    assert not_impl_root.findtext("status") == "error"
    assert (
        not_impl_root.findtext("error/code")
        == ErrorCode.SEARCH_MODE_NOT_IMPLEMENTED.value
    )
