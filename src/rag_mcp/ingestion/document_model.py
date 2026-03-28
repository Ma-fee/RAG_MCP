from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

ElementType = Literal["heading", "text", "list", "code_block", "table", "image"]
SUPPORTED_ELEMENT_TYPES = {
    "heading",
    "text",
    "list",
    "code_block",
    "table",
    "image",
}


@dataclass(frozen=True)
class Element:
    element_id: str
    element_type: str
    text: str
    heading_path: str
    section_title: str
    section_level: int
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.element_type not in SUPPORTED_ELEMENT_TYPES:
            raise ValueError(f"element_type is invalid: {self.element_type}")
        if self.section_level < 0:
            raise ValueError("section_level must be >= 0")
        if not self.heading_path.strip():
            raise ValueError("heading_path must not be empty")


@dataclass(frozen=True)
class Document:
    doc_id: str
    title: str
    relative_path: str
    file_type: str
    elements: list[Element]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    doc_id: str
    text: str
    chunk_index: int
    source_element_ids: list[str] = field(default_factory=list)
    heading_path: str = ""
    section_title: str = ""
    section_level: int = 0
    title: str = ""
    file_type: str = ""
    relative_path: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.chunk_index < 0:
            raise ValueError("chunk_index must be >= 0")
        if self.section_level < 0:
            raise ValueError("section_level must be >= 0")
        if not self.heading_path.strip():
            raise ValueError("heading_path must not be empty")
