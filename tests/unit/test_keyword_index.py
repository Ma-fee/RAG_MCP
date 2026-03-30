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


def test_bm25_rare_term_scores_higher_than_common_term(tmp_path: Path) -> None:
    from rag_mcp.indexing.keyword_index import KeywordIndex, persist_keyword_store

    # "common" appears in all 3 docs; "rare" appears only in doc-1
    entries = [
        {"text": "common word appears everywhere rare unique term", "uri": "rag://c/d#text-0", "title": "doc"},
        {"text": "common word appears everywhere nothing special", "uri": "rag://c/d#text-1", "title": "doc"},
        {"text": "common word appears everywhere nothing special", "uri": "rag://c/d#text-2", "title": "doc"},
    ]
    persist_keyword_store(index_dir=tmp_path, corpus_id="test", entries=entries)
    index = KeywordIndex.load(tmp_path)

    rare_hits = index.search("rare", top_k=1)
    common_hits = index.search("common", top_k=1)

    assert rare_hits
    assert common_hits
    assert rare_hits[0]["score"] > common_hits[0]["score"]


def test_bm25_shorter_doc_scores_higher_than_longer_for_same_hit(tmp_path: Path) -> None:
    from rag_mcp.indexing.keyword_index import KeywordIndex, persist_keyword_store

    short_doc = "target word"
    long_doc = "target " + " ".join(["padding"] * 50)
    entries = [
        {"text": short_doc, "uri": "rag://c/d#text-0", "title": "short"},
        {"text": long_doc, "uri": "rag://c/d#text-1", "title": "long"},
    ]
    persist_keyword_store(index_dir=tmp_path, corpus_id="test", entries=entries)
    index = KeywordIndex.load(tmp_path)

    hits = index.search("target", top_k=2)
    assert len(hits) == 2
    short_score = next(h["score"] for h in hits if h["uri"].endswith("#text-0"))
    long_score = next(h["score"] for h in hits if h["uri"].endswith("#text-1"))
    assert short_score > long_score


def test_bm25_no_match_returns_empty(tmp_path: Path) -> None:
    from rag_mcp.indexing.keyword_index import KeywordIndex, persist_keyword_store

    entries = [
        {"text": "hello world", "uri": "rag://c/d#text-0", "title": "doc"},
    ]
    persist_keyword_store(index_dir=tmp_path, corpus_id="test", entries=entries)
    index = KeywordIndex.load(tmp_path)

    hits = index.search("zzznomatch", top_k=5)
    assert hits == []


def test_persist_keyword_store_writes_idf_and_avgdl(tmp_path: Path) -> None:
    from rag_mcp.indexing.keyword_index import persist_keyword_store

    entries = [
        {"text": "hello world", "uri": "rag://c/d#text-0", "title": "doc"},
        {"text": "hello python", "uri": "rag://c/d#text-1", "title": "doc"},
    ]
    persist_keyword_store(index_dir=tmp_path, corpus_id="test", entries=entries)

    raw = json.loads((tmp_path / "keyword_store.json").read_text(encoding="utf-8"))
    assert "idf" in raw
    assert "avgdl" in raw
    assert isinstance(raw["idf"], dict)
    assert isinstance(raw["avgdl"], float)


def test_keyword_index_loads_legacy_format_without_error(tmp_path: Path) -> None:
    from rag_mcp.indexing.keyword_index import KeywordIndex

    # Write old-format keyword_store without idf/avgdl
    legacy = {
        "corpus_id": "test",
        "entries": [
            {"text": "legacy content hello", "uri": "rag://c/d#text-0", "title": "doc"},
        ],
    }
    (tmp_path / "keyword_store.json").write_text(json.dumps(legacy), encoding="utf-8")

    index = KeywordIndex.load(tmp_path)
    hits = index.search("hello", top_k=3)
    assert hits
    assert hits[0]["uri"] == "rag://c/d#text-0"
