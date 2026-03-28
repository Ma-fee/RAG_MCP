from __future__ import annotations

from dataclasses import dataclass, field

from rag_mcp.ingestion.document_model import Chunk, Document, Element


@dataclass(frozen=True)
class SourceDocument:
    doc_id: str
    title: str
    relative_path: str
    file_type: str
    text: str
    elements: list[Element] = field(default_factory=list)
