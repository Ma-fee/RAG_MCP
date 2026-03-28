from __future__ import annotations

import hashlib
from pathlib import Path

from rag_mcp.models import SourceDocument

SUPPORTED_EXTENSIONS = {".md", ".txt"}


def load_supported_documents(directory: Path) -> list[SourceDocument]:
    docs: list[SourceDocument] = []
    for path in sorted(directory.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        relative_path = path.relative_to(directory).as_posix()
        file_type = path.suffix.lower().lstrip(".")
        text = path.read_text(encoding="utf-8")
        docs.append(
            SourceDocument(
                doc_id=_make_doc_id(relative_path),
                title=path.name,
                relative_path=relative_path,
                file_type=file_type,
                text=text,
            )
        )
    return docs


def _make_doc_id(relative_path: str) -> str:
    return hashlib.sha1(relative_path.encode("utf-8")).hexdigest()[:16]

