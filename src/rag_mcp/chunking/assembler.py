from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from rag_mcp.models import Chunk, SourceDocument


@dataclass(frozen=True)
class _Segment:
    heading_path: str
    section_title: str
    section_level: int
    text: str
    source_element_ids: list[str]


class ChunkAssembler:
    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 120, min_chunk_length: int = 0) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be > 0")
        if chunk_overlap < 0:
            raise ValueError("chunk_overlap must be >= 0")
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be < chunk_size")
        if min_chunk_length < 0:
            raise ValueError("min_chunk_length must be >= 0")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_length = min_chunk_length

    def assemble(self, document: SourceDocument) -> list[Chunk]:
        segments = list(_group_text_segments(document, self.chunk_size, self.min_chunk_length))
        if not segments:
            fallback_text = " ".join(document.text.split()).strip()
            if not fallback_text or len(fallback_text) < self.min_chunk_length:
                return []
            segments = [
                _Segment(
                    heading_path=document.title,
                    section_title=document.title,
                    section_level=0,
                    text=fallback_text,
                    source_element_ids=[],
                )
            ]

        chunks: list[Chunk] = []
        chunk_index = 0
        for segment in segments:
            for piece in _split_text_with_overlap(
                segment.text, self.chunk_size, self.chunk_overlap
            ):
                piece_text = piece.strip()
                if not piece_text:
                    continue
                chunks.append(
                    Chunk(
                        chunk_id=f"{document.doc_id}#chunk-{chunk_index}",
                        doc_id=document.doc_id,
                        text=piece_text,
                        chunk_index=chunk_index,
                        source_element_ids=list(segment.source_element_ids),
                        heading_path=segment.heading_path,
                        section_title=segment.section_title,
                        section_level=segment.section_level,
                        title=document.title,
                        file_type=document.file_type,
                        relative_path=document.relative_path,
                    )
                )
                chunk_index += 1
        return chunks


def _group_text_segments(
    document: SourceDocument, chunk_size: int, min_chunk_length: int = 0
) -> Iterable[_Segment]:
    current_heading_path = ""
    current_section_title = ""
    current_section_level = 0
    current_text = ""
    current_ids: list[str] = []

    def flush() -> _Segment | None:
        text = " ".join(current_text.split()).strip()
        if not text or len(text) < min_chunk_length:
            return None
        return _Segment(
            heading_path=current_heading_path,
            section_title=current_section_title,
            section_level=current_section_level,
            text=text,
            source_element_ids=list(current_ids),
        )

    for element in document.elements:
        if element.element_type not in {"text", "list", "code_block", "heading", "table"}:
            continue
        text = " ".join(element.text.split()).strip()
        if not text:
            continue
        same_context = (
            element.heading_path == current_heading_path
            and element.section_title == current_section_title
            and element.section_level == current_section_level
        )
        merged_candidate = f"{current_text} {text}".strip() if current_text else text
        if current_text and (not same_context or len(merged_candidate) > chunk_size):
            segment = flush()
            if segment is not None:
                yield segment
            current_text = ""
            current_ids = []

        if not current_text:
            current_heading_path = element.heading_path
            current_section_title = element.section_title
            current_section_level = element.section_level
            current_text = text
            current_ids = [element.element_id]
        else:
            current_text = merged_candidate
            current_ids.append(element.element_id)

    tail = flush()
    if tail is not None:
        yield tail


def _split_text_with_overlap(
    text: str, chunk_size: int, chunk_overlap: int
) -> list[str]:
    cleaned = " ".join(text.split())
    if not cleaned:
        return []
    if len(cleaned) <= chunk_size:
        return [cleaned]

    pieces: list[str] = []
    start = 0
    step = max(1, chunk_size - chunk_overlap)
    length = len(cleaned)
    while start < length:
        end = min(length, start + chunk_size)
        pieces.append(cleaned[start:end])
        if end >= length:
            break
        start += step
    return pieces
