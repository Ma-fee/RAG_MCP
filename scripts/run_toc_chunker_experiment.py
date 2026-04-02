from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from rag_mcp.chunking.toc_chunker import TocAwareChunker, _extract_toc_nodes
from rag_mcp.ingestion.docling_parser import parse_document_file
from rag_mcp.models import SourceDocument


def run(pdf_path: Path, output_path: Path, min_chunk_length: int) -> dict:
    pdf_path = pdf_path.resolve()
    root_dir = pdf_path.parent
    corpus_id = _make_corpus_id(root_dir)

    doc = parse_document_file(pdf_path, root_dir=root_dir)
    source_doc = SourceDocument(
        doc_id=doc.doc_id,
        title=doc.title,
        relative_path=doc.relative_path,
        file_type=doc.file_type,
        text=" ".join(e.text for e in doc.elements if e.element_type != "heading").strip(),
        elements=doc.elements,
    )

    toc_nodes = _extract_toc_nodes(pdf_path)
    chunks = TocAwareChunker(min_chunk_length=min_chunk_length).chunk_document(
        source_doc, pdf_path
    )
    resources, element_to_resource_uri = _build_resource_entries(source_doc, corpus_id)

    chunk_entries: list[dict[str, Any]] = []
    keyword_entries: list[dict[str, Any]] = []
    uri_to_resource = {entry["uri"]: entry for entry in resources}
    for chunk in chunks:
        chunk_uri = f"rag://corpus/{corpus_id}/{source_doc.doc_id}#text-{chunk.chunk_index}"
        related_resource_uris = _chunk_related_resource_uris(chunk, element_to_resource_uri)
        resource_metadata = _resource_metadata_for_chunk(chunk, source_doc)

        for resource_uri in related_resource_uris:
            resource_entry = uri_to_resource.get(resource_uri)
            if resource_entry is None:
                continue
            related_chunks = resource_entry.setdefault("related_chunk_uris", [])
            if chunk_uri not in related_chunks:
                related_chunks.append(chunk_uri)

        chunk_entries.append(
            {
                "uri": chunk_uri,
                "chunk_id": chunk.chunk_id,
                "chunk_index": chunk.chunk_index,
                "heading_path": chunk.heading_path,
                "section_title": chunk.section_title,
                "section_level": chunk.section_level,
                "text": chunk.text,
                "text_preview": chunk.text[:240],
                "text_length": len(chunk.text),
                "source_element_ids": chunk.source_element_ids,
                "resource_metadata": resource_metadata,
                "related_resource_uris": related_resource_uris,
                "metadata": chunk.metadata,
            }
        )

        keyword_entry: dict[str, Any] = {
            "text": chunk.text,
            "title": source_doc.title,
            "uri": chunk_uri,
            "metadata": {
                "corpus_id": corpus_id,
                "doc_id": source_doc.doc_id,
                "chunk_index": chunk.chunk_index,
                "file_type": source_doc.file_type,
                "title": source_doc.title,
                "section_title": chunk.section_title,
                "heading_path": chunk.heading_path,
                "section_level": chunk.section_level,
                "relative_path": source_doc.relative_path,
                "chunk_length": len(chunk.text),
            },
            "related_resource_uris": related_resource_uris,
        }
        if resource_metadata:
            keyword_entry["resource_metadata"] = resource_metadata
        keyword_entries.append(keyword_entry)

    payload = {
        "pdf_path": str(pdf_path),
        "doc_id": doc.doc_id,
        "corpus_id": corpus_id,
        "toc_count": len(toc_nodes),
        "chunk_count": len(chunks),
        "resource_count": len(resources),
        "toc": [
            {
                "level": node.level,
                "title": node.title,
                "heading_path": node.heading_path,
                "page_start": node.page_start,
                "page_end": node.page_end,
            }
            for node in toc_nodes
        ],
        "chunks": chunk_entries,
        "resources": resources,
        "keyword_store_like": {
            "corpus_id": corpus_id,
            "entries": keyword_entries,
        },
        "resource_store_like": {
            "entries": resources,
        },
        "chunk_resource_map": [
            {
                "chunk_uri": c["uri"],
                "related_resource_uris": c["related_resource_uris"],
                "resource_metadata": c["resource_metadata"],
            }
            for c in chunk_entries
        ],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def _make_corpus_id(source_dir: Path) -> str:
    normalized = str(source_dir.resolve()).replace("\\", "/").lower()
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]


def _build_resource_entries(
    document: SourceDocument,
    corpus_id: str,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    entries: list[dict[str, Any]] = []
    element_to_uri: dict[str, str] = {}

    text_n = image_n = table_n = 0
    for element in document.elements:
        if element.element_type == "text":
            uri = f"rag://corpus/{corpus_id}/{document.doc_id}#text-res-{text_n}"
            entry = {
                "uri": uri,
                "type": "text",
                "doc_id": document.doc_id,
                "element_id": element.element_id,
                "text": element.text,
                "heading_path": element.heading_path,
                "section_title": element.section_title,
                "section_level": element.section_level,
                "related_chunk_uris": [],
            }
            entries.append(entry)
            element_to_uri[element.element_id] = uri
            text_n += 1
            continue

        if element.element_type == "image":
            uri = f"rag://corpus/{corpus_id}/{document.doc_id}#image-{image_n}"
            entry = {
                "uri": uri,
                "type": "image",
                "doc_id": document.doc_id,
                "element_id": element.element_id,
                "heading_path": element.heading_path,
                "image_path": element.metadata.get("image_path", ""),
                "page_number": element.metadata.get("page_number"),
                "related_chunk_uris": [],
            }
            entries.append(entry)
            element_to_uri[element.element_id] = uri
            image_n += 1
            continue

        if element.element_type == "table":
            uri = f"rag://corpus/{corpus_id}/{document.doc_id}#table-{table_n}"
            entry = {
                "uri": uri,
                "type": "table",
                "doc_id": document.doc_id,
                "element_id": element.element_id,
                "heading_path": element.heading_path,
                "markdown": element.metadata.get("markdown", "") or element.text,
                "data_json": element.metadata.get("data_json", ""),
                "page_number": element.metadata.get("page_number"),
                "related_chunk_uris": [],
            }
            entries.append(entry)
            element_to_uri[element.element_id] = uri
            table_n += 1

    return entries, element_to_uri


def _chunk_related_resource_uris(
    chunk: Any,
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


def _resource_metadata_for_chunk(chunk: Any, document: SourceDocument) -> dict[str, list[str]]:
    image_ids = {e.element_id for e in document.elements if e.element_type == "image"}
    table_ids = {e.element_id for e in document.elements if e.element_type == "table"}

    return {
        "table_element_ids": [eid for eid in chunk.source_element_ids if eid in table_ids],
        "image_element_ids": [eid for eid in chunk.source_element_ids if eid in image_ids],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run TOC chunker experiment on one PDF")
    parser.add_argument("pdf_path", type=Path, help="Path to PDF file")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/experiments/toc_chunker_result.json"),
        help="Output JSON path",
    )
    parser.add_argument(
        "--min-chunk-length",
        type=int,
        default=30,
        help="Minimum chunk text length",
    )
    args = parser.parse_args()

    payload = run(args.pdf_path, args.output, args.min_chunk_length)
    print(
        f"done: toc={payload['toc_count']}, chunks={payload['chunk_count']}, output={args.output.resolve()}"
    )


if __name__ == "__main__":
    main()
