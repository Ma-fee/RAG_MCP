from __future__ import annotations

import json
from pathlib import Path

import pytest

from rag_mcp.indexing.keyword_index import KeywordIndex
from rag_mcp.indexing.manifest import read_active_manifest
from rag_mcp.indexing.rebuild import rebuild_keyword_index


def _write_corpus(corpus_dir: Path) -> None:
    corpus_dir.mkdir(parents=True, exist_ok=True)
    (corpus_dir / "README.md").write_text(
        "# RFC\n\n## Design\n\nkeyword retrieval for mcp service", encoding="utf-8"
    )
    (corpus_dir / "notes.txt").write_text(
        "keyword search should return relevant chunks", encoding="utf-8"
    )


def test_rebuild_writes_active_manifest_and_keyword_store(tmp_path: Path) -> None:
    corpus_dir = tmp_path / "corpus"
    _write_corpus(corpus_dir)
    data_dir = tmp_path / "data"

    result = rebuild_keyword_index(
        source_dir=corpus_dir,
        data_dir=data_dir,
        chunk_size=64,
        chunk_overlap=8,
    )

    manifest = read_active_manifest(data_dir / "active_index.json")
    assert manifest is not None
    assert manifest["corpus_id"] == result["corpus_id"]
    assert Path(manifest["index_dir"]).exists()
    assert manifest["document_count"] == 2
    assert manifest["chunk_count"] >= 2

    keyword_index = KeywordIndex.load(Path(manifest["index_dir"]))
    hits = keyword_index.search("keyword retrieval", top_k=3)
    assert hits
    assert hits[0]["uri"].startswith(f"rag://corpus/{result['corpus_id']}/")


def test_rebuild_same_directory_keeps_stable_corpus_id(tmp_path: Path) -> None:
    corpus_dir = tmp_path / "corpus"
    _write_corpus(corpus_dir)
    data_dir = tmp_path / "data"

    first = rebuild_keyword_index(corpus_dir, data_dir, chunk_size=64, chunk_overlap=8)
    (corpus_dir / "notes.txt").write_text(
        "keyword search can be rebuilt safely with same corpus id", encoding="utf-8"
    )
    second = rebuild_keyword_index(
        corpus_dir, data_dir, chunk_size=64, chunk_overlap=8
    )

    assert first["corpus_id"] == second["corpus_id"]


def test_rebuild_failure_keeps_old_active_index(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    corpus_dir = tmp_path / "corpus"
    _write_corpus(corpus_dir)
    data_dir = tmp_path / "data"

    first = rebuild_keyword_index(corpus_dir, data_dir, chunk_size=64, chunk_overlap=8)
    old_manifest = read_active_manifest(data_dir / "active_index.json")
    assert old_manifest is not None

    def _boom(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("simulated build failure")

    monkeypatch.setattr("rag_mcp.indexing.rebuild._build_and_persist_keyword_store", _boom)

    with pytest.raises(RuntimeError):
        rebuild_keyword_index(corpus_dir, data_dir, chunk_size=64, chunk_overlap=8)

    new_manifest = read_active_manifest(data_dir / "active_index.json")
    assert new_manifest == old_manifest
    assert new_manifest["corpus_id"] == first["corpus_id"]


def test_keyword_index_store_is_json_serializable(tmp_path: Path) -> None:
    corpus_dir = tmp_path / "corpus"
    _write_corpus(corpus_dir)
    data_dir = tmp_path / "data"
    result = rebuild_keyword_index(corpus_dir, data_dir, chunk_size=64, chunk_overlap=8)

    manifest = read_active_manifest(data_dir / "active_index.json")
    assert manifest is not None
    store_file = Path(manifest["index_dir"]) / "keyword_store.json"
    raw = json.loads(store_file.read_text(encoding="utf-8"))

    assert raw["corpus_id"] == result["corpus_id"]
    assert isinstance(raw["entries"], list)
    assert raw["entries"]
