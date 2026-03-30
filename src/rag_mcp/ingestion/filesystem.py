from __future__ import annotations

import hashlib
from pathlib import Path

from rag_mcp.ingestion.docling_parser import parse_document_file_cached
from rag_mcp.models import SourceDocument

SUPPORTED_EXTENSIONS = {".md", ".txt", ".pdf"}


def load_supported_documents(directory: Path, cache_dir: Path | None = None) -> list[SourceDocument]:
    docs: list[SourceDocument] = []
    for path in sorted(directory.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        parsed = parse_document_file_cached(path, directory, cache_dir=cache_dir)
        relative_path = parsed.relative_path
        file_type = parsed.file_type
        text = " ".join(
            element.text for element in parsed.elements if element.element_type != "heading"
        ).strip()
        if not text:
            text = " ".join(element.text for element in parsed.elements).strip()
        docs.append(
            SourceDocument(
                doc_id=_make_doc_id(relative_path),
                title=parsed.title,
                relative_path=relative_path,
                file_type=file_type,
                text=text,
                elements=parsed.elements,
            )
        )
    return docs


def _make_doc_id(relative_path: str) -> str:
    return hashlib.sha1(relative_path.encode("utf-8")).hexdigest()[:16]
