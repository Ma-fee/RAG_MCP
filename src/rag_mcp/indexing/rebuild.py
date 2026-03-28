from __future__ import annotations

import hashlib
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

from rag_mcp.chunking.chunker import Chunker
from rag_mcp.indexing.keyword_index import persist_keyword_store
from rag_mcp.indexing.manifest import read_active_manifest, write_active_manifest_atomic
from rag_mcp.ingestion.filesystem import load_supported_documents
from rag_mcp.models import Chunk


def rebuild_keyword_index(
    source_dir: Path, data_dir: Path, chunk_size: int = 800, chunk_overlap: int = 120
) -> dict[str, Any]:
    source_dir = source_dir.resolve()
    data_dir = data_dir.resolve()
    index_root = data_dir / "indexes"
    index_root.mkdir(parents=True, exist_ok=True)
    active_manifest_path = data_dir / "active_index.json"
    old_manifest = read_active_manifest(active_manifest_path)

    corpus_id = _make_corpus_id(source_dir)
    temp_index_dir = index_root / f".tmp-{uuid.uuid4().hex}"
    final_index_dir = index_root / f"idx-{int(time.time() * 1000)}-{uuid.uuid4().hex[:8]}"

    try:
        result = _build_and_persist_keyword_store(
            source_dir=source_dir,
            corpus_id=corpus_id,
            index_dir=temp_index_dir,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        temp_index_dir.replace(final_index_dir)

        manifest = {
            "corpus_id": corpus_id,
            "index_dir": str(final_index_dir),
            "indexed_at": int(time.time()),
            "document_count": result["document_count"],
            "chunk_count": result["chunk_count"],
        }
        write_active_manifest_atomic(active_manifest_path, manifest)
    except Exception:
        if temp_index_dir.exists():
            shutil.rmtree(temp_index_dir, ignore_errors=True)
        raise

    if old_manifest and old_manifest.get("index_dir") != str(final_index_dir):
        old_dir = Path(old_manifest["index_dir"])
        if old_dir.exists():
            shutil.rmtree(old_dir, ignore_errors=True)

    return manifest


def _build_and_persist_keyword_store(
    source_dir: Path,
    corpus_id: str,
    index_dir: Path,
    chunk_size: int,
    chunk_overlap: int,
) -> dict[str, int]:
    documents = load_supported_documents(source_dir)
    chunker = Chunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    entries: list[dict[str, Any]] = []
    for doc in documents:
        chunks: list[Chunk] = chunker.chunk_document(doc)
        for chunk in chunks:
            entries.append(
                {
                    "text": chunk.text,
                    "title": chunk.title,
                    "uri": f"rag://corpus/{corpus_id}/{chunk.doc_id}#chunk-{chunk.chunk_index}",
                    "metadata": {
                        "corpus_id": corpus_id,
                        "doc_id": chunk.doc_id,
                        "chunk_index": chunk.chunk_index,
                        "file_type": chunk.file_type,
                        "title": chunk.title,
                        "section_title": chunk.section_title,
                        "heading_path": chunk.heading_path,
                        "section_level": chunk.section_level,
                        "relative_path": chunk.relative_path,
                        "chunk_length": len(chunk.text),
                    },
                }
            )

    persist_keyword_store(index_dir=index_dir, corpus_id=corpus_id, entries=entries)
    return {"document_count": len(documents), "chunk_count": len(entries)}


def _make_corpus_id(source_dir: Path) -> str:
    normalized = str(source_dir).replace("\\", "/").lower()
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]

