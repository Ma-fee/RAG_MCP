from __future__ import annotations

import hashlib
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

from rag_mcp.chunking.chunker import Chunker
from rag_mcp.indexing.cross_reference import build_cross_references
from rag_mcp.indexing.keyword_index import persist_keyword_store
from rag_mcp.indexing.manifest import read_active_manifest, write_active_manifest_atomic
from rag_mcp.indexing.resource_store import ResourceStore
from rag_mcp.indexing.vector_index import VectorIndex
from rag_mcp.ingestion.filesystem import load_supported_documents
from rag_mcp.models import Chunk, SourceDocument


def rebuild_keyword_index(
    source_dir: Path,
    data_dir: Path,
    chunk_size: int = 800,
    chunk_overlap: int = 120,
    min_chunk_length: int = 30,
    embedding_provider: Any | None = None,
    vlm_client: Any | None = None,
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
            min_chunk_length=min_chunk_length,
            embedding_provider=embedding_provider,
            vlm_client=vlm_client,
        )
        temp_index_dir.replace(final_index_dir)

        manifest = {
            "corpus_id": corpus_id,
            "index_dir": str(final_index_dir),
            "indexed_at": int(time.time()),
            "document_count": result["document_count"],
            "chunk_count": result["chunk_count"],
            "embedding_model": result["embedding_model"],
            "embedding_dimension": result["embedding_dimension"],
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
    min_chunk_length: int,
    embedding_provider: Any | None,
    vlm_client: Any | None = None,
) -> dict[str, int]:
    documents = sorted(
        load_supported_documents(source_dir), key=lambda item: item.relative_path
    )
    chunker = Chunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap, min_chunk_length=min_chunk_length)

    # Build ResourceStore (image/table/text resource entries) for all documents
    resource_store = ResourceStore(index_dir=index_dir, corpus_id=corpus_id, vlm_client=vlm_client)
    all_resource_entries: list[dict[str, Any]] = []
    for doc in documents:
        all_resource_entries.extend(resource_store.build(doc))
    linked_entries = build_cross_references(all_resource_entries)
    # _persist is deferred until after table.related backfill below

    entries: list[dict[str, Any]] = []
    element_id_to_chunk_uri: dict[str, str] = {}
    for doc in documents:
        stable_doc_id = _stable_doc_id(doc.relative_path)
        chunks: list[Chunk] = chunker.chunk_document(doc)
        attachment_meta_by_chunk = _build_attachment_metadata(doc, chunks)
        for chunk in chunks:
            chunk_uri = f"rag://corpus/{corpus_id}/{stable_doc_id}#text-{chunk.chunk_index}"
            entry: dict[str, Any] = {
                "text": chunk.text,
                "title": chunk.title,
                "uri": chunk_uri,
                "metadata": {
                    "corpus_id": corpus_id,
                    "doc_id": stable_doc_id,
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
            attachment_metadata = attachment_meta_by_chunk.get(chunk.chunk_index)
            if attachment_metadata:
                entry["resource_metadata"] = attachment_metadata
                for elem_id in attachment_metadata.get("table_element_ids", []):
                    element_id_to_chunk_uri[elem_id] = chunk_uri
            entries.append(entry)

    # Backfill table.related with the chunk URI that absorbed the table
    for linked_entry in linked_entries:
        if linked_entry["type"] == "table":
            elem_id = linked_entry.get("element_id", "")
            chunk_uri = element_id_to_chunk_uri.get(elem_id)
            if chunk_uri and chunk_uri not in linked_entry["related"]:
                linked_entry["related"].append(chunk_uri)
    resource_store._persist(linked_entries)

    persist_keyword_store(index_dir=index_dir, corpus_id=corpus_id, entries=entries)

    if embedding_provider is not None and entries:
        vector_index = VectorIndex(index_dir=index_dir)
        vector_index.reset()
        vector_entries = [
            {
                "id": _entry_id(entry),
                "text": entry["text"],
                "uri": entry["uri"],
                "title": entry["title"],
                "metadata": entry["metadata"],
            }
            for entry in entries
        ]
        embeddings = embedding_provider.embed_documents(
            [item["text"] for item in vector_entries]
        )
        vector_index.upsert_chunks(vector_entries, embeddings)

    return {
        "document_count": len(documents),
        "chunk_count": len(entries),
        "embedding_model": (
            embedding_provider.model_name() if embedding_provider is not None else None
        ),
        "embedding_dimension": (
            embedding_provider.embedding_dimension()
            if embedding_provider is not None
            else None
        ),
    }


def _make_corpus_id(source_dir: Path) -> str:
    normalized = str(source_dir).replace("\\", "/").lower()
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]


def _entry_id(entry: dict[str, Any]) -> str:
    meta = entry["metadata"]
    return f"{meta['doc_id']}#text-{meta['chunk_index']}"


def _build_attachment_metadata(
    document: SourceDocument, chunks: list[Chunk]
) -> dict[int, dict[str, list[str]]]:
    if not document.elements or not chunks:
        return {}

    element_to_chunk_index: dict[str, int] = {}
    for chunk in chunks:
        for element_id in chunk.source_element_ids:
            element_to_chunk_index[element_id] = chunk.chunk_index

    if not element_to_chunk_index:
        return {}

    last_text_chunk_by_context: dict[tuple[str, str, int], int] = {}
    attachments: dict[int, dict[str, list[str]]] = {}

    for element in document.elements:
        context = (element.heading_path, element.section_title, element.section_level)
        text_chunk_index = element_to_chunk_index.get(element.element_id)
        if text_chunk_index is not None:
            last_text_chunk_by_context[context] = text_chunk_index
            if element.element_type in {"table", "image"}:
                bucket = attachments.setdefault(
                    text_chunk_index, {"table_element_ids": [], "image_element_ids": []}
                )
                if element.element_type == "table":
                    bucket["table_element_ids"].append(element.element_id)
                else:
                    bucket["image_element_ids"].append(element.element_id)
            continue
        if element.element_type not in {"table", "image"}:
            continue
        target_chunk_index = last_text_chunk_by_context.get(context)
        if target_chunk_index is None:
            continue
        bucket = attachments.setdefault(
            target_chunk_index, {"table_element_ids": [], "image_element_ids": []}
        )
        if element.element_type == "table":
            bucket["table_element_ids"].append(element.element_id)
        if element.element_type == "image":
            bucket["image_element_ids"].append(element.element_id)

    compact: dict[int, dict[str, list[str]]] = {}
    for chunk_index, bucket in attachments.items():
        payload = {key: value for key, value in bucket.items() if value}
        if payload:
            compact[chunk_index] = payload
    return compact


def _stable_doc_id(relative_path: str) -> str:
    normalized = str(relative_path).replace("\\", "/").lower()
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]
