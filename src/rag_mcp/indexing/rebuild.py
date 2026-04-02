from __future__ import annotations

import hashlib
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

from rag_mcp.chunking.toc_chunker import TocAwareChunker
from rag_mcp.indexing.keyword_index import persist_keyword_store
from rag_mcp.indexing.manifest import read_active_manifest, write_active_manifest_atomic
from rag_mcp.indexing.resource_store import ResourceStore
from rag_mcp.indexing.vector_index import VectorIndex
from rag_mcp.ingestion.filesystem import load_supported_documents
from rag_mcp.models import Chunk


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
    min_chunk_length: int,
    embedding_provider: Any | None,
    vlm_client: Any | None = None,
) -> dict[str, int]:
    documents = sorted(load_supported_documents(source_dir), key=lambda item: item.relative_path)

    # Build ResourceStore (image/table/text resource entries) for all documents
    resource_store = ResourceStore(index_dir=index_dir, corpus_id=corpus_id, vlm_client=vlm_client)
    all_resource_entries: list[dict[str, Any]] = []
    for doc in documents:
        all_resource_entries.extend(resource_store.build(doc))
    resource_entry_by_uri = {entry["uri"]: entry for entry in all_resource_entries}

    entries: list[dict[str, Any]] = []
    for doc in documents:
        stable_doc_id = _stable_doc_id(doc.relative_path)
        doc_element_to_resource_uri = _build_doc_element_resource_uri_map(doc, all_resource_entries)
        if doc.file_type != "pdf":
            raise RuntimeError(
                f"TOC-only indexing supports PDF only, got {doc.file_type}: {doc.relative_path}"
            )

        try:
            pdf_path = source_dir / doc.relative_path
            if not pdf_path.exists():
                raise FileNotFoundError(f"pdf file not found: {pdf_path}")

            chunks = TocAwareChunker(min_chunk_length=min_chunk_length).chunk_document(
                doc, pdf_path
            )
            if not chunks:
                raise ValueError(
                    f"toc chunking produced no chunks for {doc.relative_path}; ensure PDF has embedded TOC and enough text"
                )
        except Exception as exc:
            raise RuntimeError(
                f"TOC chunking failed for PDF {doc.relative_path}"
            ) from exc

        for chunk in chunks:
            chunk_uri = f"rag://corpus/{corpus_id}/{stable_doc_id}#text-{chunk.chunk_index}"
            related_resource_uris = _chunk_related_resource_uris(
                chunk=chunk,
                element_to_resource_uri=doc_element_to_resource_uri,
            )
            resource_metadata = _resource_metadata_for_chunk(chunk=chunk, document=doc)

            for resource_uri in related_resource_uris:
                resource_entry = resource_entry_by_uri.get(resource_uri)
                if resource_entry is None:
                    continue
                related = resource_entry.setdefault("related", [])
                if chunk_uri not in related:
                    related.append(chunk_uri)

            entry: dict[str, Any] = {
                "text": chunk.text,
                "title": chunk.title,
                "uri": chunk_uri,
                "metadata": {
                    "corpus_id": corpus_id,
                    "doc_id": stable_doc_id,
                    "chunk_index": chunk.chunk_index,
                    "file_type": chunk.file_type,
                    "section_title": chunk.section_title,
                    "heading_path": chunk.heading_path,
                    "section_level": chunk.section_level,
                    "relative_path": chunk.relative_path,
                    "chunk_length": len(chunk.text),
                },
                "related_resource_uris": related_resource_uris,
            }
            if resource_metadata:
                entry["resource_metadata"] = resource_metadata
            entries.append(entry)

    resource_store._persist(all_resource_entries)

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


def _build_doc_element_resource_uri_map(
    document: Any,
    resource_entries: list[dict[str, Any]],
) -> dict[str, str]:
    element_to_uri: dict[str, str] = {}
    for entry in resource_entries:
        if entry.get("doc_id") != document.doc_id:
            continue
        element_id = entry.get("element_id")
        uri = entry.get("uri")
        if not element_id or not uri:
            continue
        element_to_uri[element_id] = uri
    return element_to_uri


def _chunk_related_resource_uris(
    chunk: Chunk,
    element_to_resource_uri: dict[str, str],
) -> list[str]:
    uris: list[str] = []
    for element_id in chunk.source_element_ids:
        resource_uri = element_to_resource_uri.get(element_id)
        if (
            resource_uri
            and ("#image-" in resource_uri or "#table-" in resource_uri)
            and resource_uri not in uris
        ):
            uris.append(resource_uri)
    return uris


def _resource_metadata_for_chunk(chunk: Chunk, document: Any) -> dict[str, list[str]]:
    image_ids = {e.element_id for e in document.elements if e.element_type == "image"}
    table_ids = {e.element_id for e in document.elements if e.element_type == "table"}

    metadata = {
        "table_element_ids": [eid for eid in chunk.source_element_ids if eid in table_ids],
        "image_element_ids": [eid for eid in chunk.source_element_ids if eid in image_ids],
    }
    return {k: v for k, v in metadata.items() if v}


def _stable_doc_id(relative_path: str) -> str:
    normalized = str(relative_path).replace("\\", "/").lower()
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]
