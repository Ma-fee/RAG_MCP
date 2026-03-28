from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from rag_mcp.errors import ErrorCode, ServiceException
from rag_mcp.indexing.rebuild import rebuild_keyword_index
from rag_mcp.retrieval.service import RetrievalService
from rag_mcp.transport.stdio_server import StdioServer


class _FakeEmbeddingProvider:
    def __init__(self, model: str = "fake-v1", dimension: int = 3) -> None:
        self._model = model
        self._dimension = dimension

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            lowered = text.lower()
            if "alpha" in lowered:
                vectors.append([1.0, 0.0, 0.0])
            elif "beta" in lowered:
                vectors.append([0.0, 1.0, 0.0])
            else:
                vectors.append([0.0, 0.0, 1.0])
        return vectors

    def embed_query(self, text: str) -> list[float]:
        lowered = text.lower()
        if "alpha" in lowered:
            return [1.0, 0.0, 0.0]
        if "beta" in lowered:
            return [0.0, 1.0, 0.0]
        return [0.0, 0.0, 1.0]

    def model_name(self) -> str:
        return self._model

    def embedding_dimension(self) -> int:
        return self._dimension


def _prepare_corpus(corpus_dir: Path) -> None:
    corpus_dir.mkdir(parents=True, exist_ok=True)
    (corpus_dir / "reference.md").write_text(
        "# Retrieval Reference\n\n## Alpha\n\nAlpha topic and semantic retrieval.\n\n## Beta\n\nBeta keyword section.",
        encoding="utf-8",
    )


def test_vector_and_keyword_modes_return_same_contract(tmp_path: Path) -> None:
    corpus_dir = tmp_path / "corpus"
    data_dir = tmp_path / "data"
    _prepare_corpus(corpus_dir)
    provider = _FakeEmbeddingProvider()

    rebuild_keyword_index(
        source_dir=corpus_dir,
        data_dir=data_dir,
        chunk_size=80,
        chunk_overlap=10,
        embedding_provider=provider,
    )
    retrieval = RetrievalService(data_dir=data_dir, embedding_provider=provider)

    keyword_payload = retrieval.search("beta keyword", mode="keyword", top_k=3)
    vector_payload = retrieval.search("alpha semantic", mode="vector", top_k=3)

    assert keyword_payload["mode"] == "keyword"
    assert vector_payload["mode"] == "vector"
    assert keyword_payload["result_count"] >= 1
    assert vector_payload["result_count"] >= 1

    keyword_result = keyword_payload["results"][0]
    vector_result = vector_payload["results"][0]
    required_fields = {"text", "title", "uri", "score", "metadata"}
    assert required_fields <= keyword_result.keys()
    assert required_fields <= vector_result.keys()


def test_reserved_modes_report_not_implemented(tmp_path: Path) -> None:
    corpus_dir = tmp_path / "corpus"
    data_dir = tmp_path / "data"
    _prepare_corpus(corpus_dir)
    provider = _FakeEmbeddingProvider()
    rebuild_keyword_index(
        source_dir=corpus_dir,
        data_dir=data_dir,
        chunk_size=80,
        chunk_overlap=10,
        embedding_provider=provider,
    )
    retrieval = RetrievalService(data_dir=data_dir, embedding_provider=provider)

    for mode in ("hybrid", "rerank"):
        with pytest.raises(ServiceException) as exc:
            retrieval.search("alpha", mode=mode, top_k=3)
        assert exc.value.error.code == ErrorCode.SEARCH_MODE_NOT_IMPLEMENTED


def test_stdio_server_xml_output_for_vector_mode(tmp_path: Path) -> None:
    corpus_dir = tmp_path / "corpus"
    data_dir = tmp_path / "data"
    _prepare_corpus(corpus_dir)
    provider = _FakeEmbeddingProvider()
    server = StdioServer(data_dir=data_dir, embedding_provider=provider)

    rebuild_keyword_index(
        source_dir=corpus_dir,
        data_dir=data_dir,
        chunk_size=80,
        chunk_overlap=10,
        embedding_provider=provider,
    )
    xml_text = server.rag_search(query="alpha semantic", mode="vector", top_k=3)

    root = ET.fromstring(xml_text)
    assert root.findtext("status") == "ok"
    assert root.findtext("data/search-results/mode") == "vector"
    assert int(root.findtext("data/search-results/result_count") or "0") >= 1
