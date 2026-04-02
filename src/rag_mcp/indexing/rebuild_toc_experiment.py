from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from pathlib import Path
from typing import Any

from rag_mcp.ingestion.document_model import Chunk, Element
from rag_mcp.ingestion.filesystem import load_supported_documents
from rag_mcp.models import SourceDocument


_HEADING_NUM_RE = re.compile(r"^(?P<num>\d+(?:\.\d+)*)\b")


def rebuild_toc_experiment_index(
    source_dir: Path,
    data_dir: Path,
    min_chunk_length: int = 30,
    vlm_client: Any | None = None,
) -> dict[str, Any]:
    """Experimental pipeline: chunk by numbered headings and map chunk<->resource URIs.

    This function intentionally does not touch active_index.json or existing MCP handlers.
    """
    source_dir = Path(source_dir).resolve()
    data_dir = Path(data_dir).resolve()

    corpus_id = _make_corpus_id(source_dir)
    experiment_dir = (
        data_dir
        / "experiments"
        / f"toc-boundary-{int(time.time() * 1000)}-{uuid.uuid4().hex[:8]}"
    )
    experiment_dir.mkdir(parents=True, exist_ok=True)

    documents = sorted(load_supported_documents(source_dir), key=lambda d: d.relative_path)

    resource_entries: list[dict[str, Any]] = []
    chunk_entries: list[dict[str, Any]] = []
    element_to_resource_uri: dict[str, str] = {}

    for doc in documents:
        stable_doc_id = _stable_doc_id(doc.relative_path)
        doc_resource_entries, doc_element_to_resource = _build_resource_entries(
            doc=doc,
            corpus_id=corpus_id,
            stable_doc_id=stable_doc_id,
            vlm_client=vlm_client,
        )
        resource_entries.extend(doc_resource_entries)
        element_to_resource_uri.update(doc_element_to_resource)

        chunks = chunk_by_numbered_headings(doc, min_chunk_length=min_chunk_length)
        text_ids = {e.element_id for e in doc.elements if e.element_type == "text"}
        image_ids = {e.element_id for e in doc.elements if e.element_type == "image"}
        table_ids = {e.element_id for e in doc.elements if e.element_type == "table"}
        for chunk in chunks:
            chunk_uri = f"rag://corpus/{corpus_id}/{stable_doc_id}#text-{chunk.chunk_index}"
            related_resource_uris = _chunk_related_resource_uris(chunk, element_to_resource_uri)
            chunk_entries.append(
                {
                    "uri": chunk_uri,
                    "text": chunk.text,
                    "title": doc.title,
                    "metadata": {
                        "corpus_id": corpus_id,
                        "doc_id": stable_doc_id,
                        "chunk_index": chunk.chunk_index,
                        "file_type": doc.file_type,
                        "relative_path": doc.relative_path,
                        "heading_path": chunk.heading_path,
                        "section_title": chunk.section_title,
                        "section_level": chunk.section_level,
                        "chunk_length": len(chunk.text),
                    },
                    "resource_metadata": {
                        "table_element_ids": [
                            eid for eid in chunk.source_element_ids if eid in table_ids
                        ],
                        "image_element_ids": [
                            eid for eid in chunk.source_element_ids if eid in image_ids
                        ],
                        "text_element_ids": [
                            eid for eid in chunk.source_element_ids if eid in text_ids
                        ],
                    },
                    "related_resource_uris": related_resource_uris,
                }
            )

    uri_to_chunk: dict[str, dict[str, Any]] = {entry["uri"]: entry for entry in chunk_entries}
    for entry in chunk_entries:
        chunk_uri = entry["uri"]
        for resource_uri in entry["related_resource_uris"]:
            resource = next((r for r in resource_entries if r["uri"] == resource_uri), None)
            if resource is None:
                continue
            if chunk_uri not in resource["related"]:
                resource["related"].append(chunk_uri)
            if resource_uri not in uri_to_chunk[chunk_uri]["related_resource_uris"]:
                uri_to_chunk[chunk_uri]["related_resource_uris"].append(resource_uri)

    chunk_store_path = experiment_dir / "keyword_store.experiment.json"
    chunk_store_path.write_text(
        json.dumps({"corpus_id": corpus_id, "entries": chunk_entries}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    resource_store_path = experiment_dir / "resource_store.experiment.json"
    resource_store_path.write_text(
        json.dumps({"entries": resource_entries}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    mapping_path = experiment_dir / "chunk_resource_map.json"
    mapping_payload = {
        "mappings": [
            {
                "chunk_uri": chunk["uri"],
                "related_resource_uris": chunk.get("related_resource_uris", []),
                "source_element_ids": chunk.get("resource_metadata", {}),
            }
            for chunk in chunk_entries
        ]
    }
    mapping_path.write_text(
        json.dumps(mapping_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return {
        "corpus_id": corpus_id,
        "experiment_dir": str(experiment_dir),
        "document_count": len(documents),
        "chunk_count": len(chunk_entries),
        "resource_count": len(resource_entries),
        "chunk_store": str(chunk_store_path),
        "resource_store": str(resource_store_path),
        "chunk_resource_map": str(mapping_path),
    }


def chunk_by_numbered_headings(
    document: SourceDocument,
    min_chunk_length: int = 30,
) -> list[Chunk]:
    """Split document by numbered heading boundaries, e.g. 1.5.3 ...

    Headings without numeric prefix (e.g. 'CAUTION') are treated as normal content.
    """
    elements = list(document.elements)
    if not elements:
        text = " ".join(document.text.split()).strip()
        if not text or len(text) < min_chunk_length:
            return []
        return [
            Chunk(
                chunk_id=f"{document.doc_id}#exp-0",
                doc_id=document.doc_id,
                text=text,
                chunk_index=0,
                source_element_ids=[],
                heading_path=document.title,
                section_title=document.title,
                section_level=0,
                title=document.title,
                file_type=document.file_type,
                relative_path=document.relative_path,
            )
        ]

    chunks: list[Chunk] = []
    current_elements: list[Element] = []
    current_section_title = document.title
    current_heading_path = document.title
    current_section_level = 0

    def flush() -> None:
        nonlocal current_elements
        if not current_elements:
            return
        text = _assemble_chunk_text(current_elements)
        if not text or len(text) < min_chunk_length:
            current_elements = []
            return
        chunk_index = len(chunks)
        chunks.append(
            Chunk(
                chunk_id=f"{document.doc_id}#exp-{chunk_index}",
                doc_id=document.doc_id,
                text=text,
                chunk_index=chunk_index,
                source_element_ids=[e.element_id for e in current_elements],
                heading_path=current_heading_path,
                section_title=current_section_title,
                section_level=current_section_level,
                title=document.title,
                file_type=document.file_type,
                relative_path=document.relative_path,
            )
        )
        current_elements = []

    for element in elements:
        if element.element_type == "heading" and _is_numbered_heading(element.text):
            flush()
            current_section_title = element.text.strip() or document.title
            current_heading_path = element.heading_path or current_section_title
            current_section_level = _heading_numeric_depth(element.text)
            current_elements = [element]
            continue
        current_elements.append(element)

    flush()
    return chunks


def _assemble_chunk_text(elements: list[Element]) -> str:
    parts: list[str] = []
    for e in elements:
        if e.element_type in {"heading", "text", "list", "code_block"}:
            t = e.text.strip()
            if t:
                parts.append(t)
        elif e.element_type == "table":
            md = str(e.metadata.get("markdown") or e.text).strip()
            if md:
                parts.append(md)
        elif e.element_type == "image":
            caption = str(e.metadata.get("caption") or e.text).strip()
            parts.append(f"[IMAGE] {caption}" if caption else "[IMAGE]")
    return "\n".join(parts).strip()


def _is_numbered_heading(text: str) -> bool:
    return _HEADING_NUM_RE.match(text.strip()) is not None


def _heading_numeric_depth(text: str) -> int:
    m = _HEADING_NUM_RE.match(text.strip())
    if not m:
        return 0
    return len(m.group("num").split("."))


def _chunk_related_resource_uris(
    chunk: Chunk, element_to_resource_uri: dict[str, str]
) -> list[str]:
    uris: list[str] = []
    for element_id in chunk.source_element_ids:
        resource_uri = element_to_resource_uri.get(element_id)
        if resource_uri and resource_uri not in uris:
            uris.append(resource_uri)
    return uris


def _build_resource_entries(
    doc: SourceDocument,
    corpus_id: str,
    stable_doc_id: str,
    vlm_client: Any | None,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    entries: list[dict[str, Any]] = []
    element_to_uri: dict[str, str] = {}

    text_n = image_n = table_n = 0

    for element in doc.elements:
        if element.element_type == "text":
            uri = f"rag://corpus/{corpus_id}/{stable_doc_id}#text-res-{text_n}"
            entry = {
                "uri": uri,
                "type": "text",
                "doc_id": stable_doc_id,
                "element_id": element.element_id,
                "text": element.text,
                "heading_path": element.heading_path,
                "section_title": element.section_title,
                "section_level": element.section_level,
                "related": [],
            }
            entries.append(entry)
            element_to_uri[element.element_id] = uri
            text_n += 1
            continue

        if element.element_type == "image":
            uri = f"rag://corpus/{corpus_id}/{stable_doc_id}#image-{image_n}"
            image_path = element.metadata.get("image_path", "")
            desc = ""
            if vlm_client and image_path:
                try:
                    desc = vlm_client.describe_image(Path(image_path))
                except Exception:
                    desc = ""
            entry = {
                "uri": uri,
                "type": "image",
                "doc_id": stable_doc_id,
                "element_id": element.element_id,
                "heading_path": element.heading_path,
                "caption": element.metadata.get("caption", ""),
                "image_path": image_path,
                "page_number": element.metadata.get("page_number"),
                "vlm_description": desc,
                "related": [],
            }
            entries.append(entry)
            element_to_uri[element.element_id] = uri
            image_n += 1
            continue

        if element.element_type == "table":
            uri = f"rag://corpus/{corpus_id}/{stable_doc_id}#table-{table_n}"
            entry = {
                "uri": uri,
                "type": "table",
                "doc_id": stable_doc_id,
                "element_id": element.element_id,
                "heading_path": element.heading_path,
                "markdown": element.metadata.get("markdown", "") or element.text,
                "data_json": element.metadata.get("data_json", ""),
                "caption": element.metadata.get("caption", ""),
                "page_number": element.metadata.get("page_number"),
                "related": [],
            }
            entries.append(entry)
            element_to_uri[element.element_id] = uri
            table_n += 1

    return entries, element_to_uri


def _make_corpus_id(source_dir: Path) -> str:
    normalized = str(source_dir).replace("\\", "/").lower()
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]


def _stable_doc_id(relative_path: str) -> str:
    normalized = str(relative_path).replace("\\", "/").lower()
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]
