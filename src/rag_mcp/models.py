from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SourceDocument:
    doc_id: str
    title: str
    relative_path: str
    file_type: str
    text: str


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    doc_id: str
    text: str
    chunk_index: int
    title: str
    file_type: str
    relative_path: str
    heading_path: str
    section_title: str
    section_level: int
    metadata: dict[str, Any] = field(default_factory=dict)

