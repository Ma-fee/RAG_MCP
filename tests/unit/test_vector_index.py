from __future__ import annotations

from pathlib import Path

from rag_mcp.indexing.manifest import read_active_manifest
from rag_mcp.indexing.rebuild import rebuild_keyword_index
from rag_mcp.indexing.vector_index import VectorIndex
from rag_mcp.retrieval.service import RetrievalService


class _FakeEmbeddingProvider:
    def __init__(self, model: str = "fake-embed", dimension: int = 3) -> None:
        self._model = model
        self._dimension = dimension

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for i, _ in enumerate(texts):
            if i % 3 == 0:
                vectors.append([1.0, 0.0, 0.0])
            elif i % 3 == 1:
                vectors.append([0.0, 1.0, 0.0])
            else:
                vectors.append([0.0, 0.0, 1.0])
        return vectors

    def embed_query(self, text: str) -> list[float]:
        if "alpha" in text:
            return [1.0, 0.0, 0.0]
        if "beta" in text:
            return [0.0, 1.0, 0.0]
        return [0.0, 0.0, 1.0]

    def model_name(self) -> str:
        return self._model

    def embedding_dimension(self) -> int:
        return self._dimension


def _write_corpus(corpus_dir: Path) -> None:
    corpus_dir.mkdir(parents=True, exist_ok=True)
    (corpus_dir / "reference.md").write_text(
        "# Reference\n\nalpha topic paragraph\n\nbeta topic paragraph",
        encoding="utf-8",
    )


def test_vector_index_upsert_and_search_ranks_by_similarity(tmp_path: Path) -> None:
    index_dir = tmp_path / "index"
    vector_index = VectorIndex(index_dir=index_dir)
    vector_index.reset()
    vector_index.upsert_chunks(
        entries=[
            {"id": "a", "text": "alpha", "uri": "rag://a", "title": "A", "metadata": {}},
            {"id": "b", "text": "beta", "uri": "rag://b", "title": "B", "metadata": {}},
        ],
        embeddings=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
    )

    hits = vector_index.search_by_vector([1.0, 0.0, 0.0], top_k=2)

    assert len(hits) == 2
    assert hits[0]["id"] == "a"
    assert hits[0]["score"] >= hits[1]["score"]


def test_rebuild_pipeline_persists_vector_store(tmp_path: Path) -> None:
    corpus_dir = tmp_path / "corpus"
    data_dir = tmp_path / "data"
    _write_corpus(corpus_dir)
    provider = _FakeEmbeddingProvider(model="fake-v1", dimension=3)

    rebuild_keyword_index(
        source_dir=corpus_dir,
        data_dir=data_dir,
        chunk_size=64,
        chunk_overlap=8,
        embedding_provider=provider,
    )

    manifest = read_active_manifest(data_dir / "active_index.json")
    assert manifest is not None
    vector_index = VectorIndex(index_dir=Path(manifest["index_dir"]))
    hits = vector_index.search_by_vector([1.0, 0.0, 0.0], top_k=2)
    assert hits


def test_rebuild_pipeline_overwrites_old_vector_index(tmp_path: Path) -> None:
    corpus_dir = tmp_path / "corpus"
    data_dir = tmp_path / "data"
    _write_corpus(corpus_dir)
    provider = _FakeEmbeddingProvider(model="fake-v1", dimension=3)

    first = rebuild_keyword_index(
        source_dir=corpus_dir,
        data_dir=data_dir,
        chunk_size=64,
        chunk_overlap=8,
        embedding_provider=provider,
    )
    first_index_dir = Path(first["index_dir"])
    assert first_index_dir.exists()

    (corpus_dir / "reference.md").write_text(
        "# Reference\n\nalpha changed paragraph",
        encoding="utf-8",
    )
    second = rebuild_keyword_index(
        source_dir=corpus_dir,
        data_dir=data_dir,
        chunk_size=64,
        chunk_overlap=8,
        embedding_provider=provider,
    )

    assert Path(second["index_dir"]).exists()
    assert not first_index_dir.exists()


def test_manifest_records_embedding_model_and_dimension(tmp_path: Path) -> None:
    corpus_dir = tmp_path / "corpus"
    data_dir = tmp_path / "data"
    _write_corpus(corpus_dir)
    provider = _FakeEmbeddingProvider(model="fake-v2", dimension=6)

    rebuild_keyword_index(
        source_dir=corpus_dir,
        data_dir=data_dir,
        chunk_size=64,
        chunk_overlap=8,
        embedding_provider=provider,
    )

    manifest = read_active_manifest(data_dir / "active_index.json")
    assert manifest is not None
    assert manifest["embedding_model"] == "fake-v2"
    assert manifest["embedding_dimension"] == 6


def test_retrieval_still_works_with_embedding_config_difference(
    tmp_path: Path,
) -> None:
    corpus_dir = tmp_path / "corpus"
    data_dir = tmp_path / "data"
    _write_corpus(corpus_dir)
    index_provider = _FakeEmbeddingProvider(model="fake-v1", dimension=3)
    query_provider = _FakeEmbeddingProvider(model="fake-v2", dimension=6)

    rebuild_keyword_index(
        source_dir=corpus_dir,
        data_dir=data_dir,
        chunk_size=64,
        chunk_overlap=8,
        embedding_provider=index_provider,
    )

    retrieval = RetrievalService(data_dir=data_dir, embedding_provider=query_provider)
    payload = retrieval.search(query="alpha", top_k=2)
    assert payload["result_count"] >= 1
    assert payload["mode"] == "rerank"
