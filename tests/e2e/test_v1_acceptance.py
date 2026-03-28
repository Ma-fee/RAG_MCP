from __future__ import annotations

import json
from pathlib import Path
from urllib import request
import xml.etree.ElementTree as ET

from rag_mcp.transport.http_server import start_http_server_if_enabled
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


def _write_corpus(corpus_dir: Path) -> None:
    corpus_dir.mkdir(parents=True, exist_ok=True)
    (corpus_dir / "reference.md").write_text(
        "# Retrieval Reference\n\n## Alpha\n\nAlpha topic and semantic retrieval.\n\n## Beta\n\nBeta keyword section.",
        encoding="utf-8",
    )


def _parse_status(xml_text: str) -> str:
    return ET.fromstring(xml_text).findtext("status") or ""


def _first_uri(xml_text: str) -> str:
    root = ET.fromstring(xml_text)
    return root.findtext("data/search-results/results/item/uri") or ""


def _http_call(endpoint: str, tool: str, args: dict[str, object]) -> str:
    payload = {"tool": tool, "args": args}
    req = request.Request(
        url=endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=5) as resp:
        return resp.read().decode("utf-8")


def test_v1_acceptance_stdio_and_http_end_to_end(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    assert (repo_root / "scripts" / "e2e_phase4_smoke.sh").exists()

    corpus_dir = tmp_path / "corpus"
    data_dir = tmp_path / "data"
    _write_corpus(corpus_dir)
    provider = _FakeEmbeddingProvider()

    stdio = StdioServer(data_dir=data_dir, embedding_provider=provider)

    stdio_rebuild = stdio.rag_rebuild_index(str(corpus_dir))
    assert _parse_status(stdio_rebuild) == "ok"

    stdio_keyword = stdio.rag_search("beta keyword", mode="keyword", top_k=3)
    stdio_vector = stdio.rag_search("alpha semantic", mode="vector", top_k=3)
    assert _parse_status(stdio_keyword) == "ok"
    assert _parse_status(stdio_vector) == "ok"
    uri = _first_uri(stdio_keyword)
    assert uri
    stdio_read = stdio.rag_read_resource(uri)
    assert _parse_status(stdio_read) == "ok"

    http_server = start_http_server_if_enabled(
        enable_http=True,
        data_dir=data_dir,
        host="127.0.0.1",
        port=0,
        embedding_provider=provider,
    )
    assert http_server is not None
    try:
        endpoint = http_server.endpoint_url()
        http_rebuild = _http_call(
            endpoint,
            "rag_rebuild_index",
            {"directory_path": str(corpus_dir)},
        )
        assert _parse_status(http_rebuild) == "ok"

        http_keyword = _http_call(
            endpoint,
            "rag_search",
            {"query": "beta keyword", "mode": "keyword", "top_k": 3},
        )
        http_vector = _http_call(
            endpoint,
            "rag_search",
            {"query": "alpha semantic", "mode": "vector", "top_k": 3},
        )
        assert _parse_status(http_keyword) == "ok"
        assert _parse_status(http_vector) == "ok"

        http_uri = _first_uri(http_keyword)
        assert http_uri
        http_read = _http_call(endpoint, "rag_read_resource", {"uri": http_uri})
        assert _parse_status(http_read) == "ok"
    finally:
        http_server.close()
