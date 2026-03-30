from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from rag_mcp.chunking.assembler import ChunkAssembler
from rag_mcp.models import Chunk, SourceDocument


@dataclass(frozen=True)
class _Section:
    heading_path: str
    section_title: str
    section_level: int
    text: str


class Chunker:
    def __init__(
        self,
        chunk_size: int = 800,
        chunk_overlap: int = 120,
        min_chunk_length: int = 0,
        source_dir: Path | None = None,
    ) -> None:
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
        self.source_dir = source_dir

    def chunk_document(self, document: SourceDocument) -> list[Chunk]:
        # For PDFs with embedded TOC, use TocAwareChunker for semantic boundaries
        if document.file_type == "pdf" and self.source_dir is not None:
            from rag_mcp.chunking.toc_chunker import TocAwareChunker
            pdf_path = self.source_dir / document.relative_path
            if pdf_path.exists():
                toc_chunks = TocAwareChunker(
                    min_chunk_length=self.min_chunk_length
                ).chunk_document(document, pdf_path)
                if toc_chunks:
                    return toc_chunks

        if document.elements:
            return ChunkAssembler(
                chunk_size=self.chunk_size, chunk_overlap=self.chunk_overlap, min_chunk_length=self.min_chunk_length
            ).assemble(document)

        if document.file_type == "md":
            sections = list(_parse_markdown_sections(document.text, document.title))
        else:
            sections = [
                _Section(
                    heading_path=document.title,
                    section_title=document.title,
                    section_level=0,
                    text=document.text,
                )
            ]

        chunks: list[Chunk] = []
        chunk_index = 0
        for section in sections:
            for piece in _split_text_with_overlap(
                section.text, self.chunk_size, self.chunk_overlap
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
                        title=document.title,
                        file_type=document.file_type,
                        relative_path=document.relative_path,
                        heading_path=section.heading_path,
                        section_title=section.section_title,
                        section_level=section.section_level,
                    )
                )
                chunk_index += 1
        return chunks


def _parse_markdown_sections(text: str, fallback_title: str) -> Iterable[_Section]:
    heading_stack: list[str] = []
    current_path = fallback_title
    current_title = fallback_title
    current_level = 0
    buffer: list[str] = []

    def flush() -> _Section | None:
        section_text = "\n".join(buffer).strip()
        if not section_text:
            return None
        return _Section(
            heading_path=current_path,
            section_title=current_title,
            section_level=current_level,
            text=section_text,
        )

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.lstrip()
        if not stripped.startswith("#"):
            buffer.append(line)
            continue

        heading_marks = len(stripped) - len(stripped.lstrip("#"))
        if heading_marks <= 0 or heading_marks > 6:
            buffer.append(line)
            continue
        if len(stripped) > heading_marks and stripped[heading_marks] != " ":
            buffer.append(line)
            continue

        previous = flush()
        if previous is not None:
            yield previous
        buffer.clear()

        heading_title = stripped[heading_marks:].strip() or fallback_title
        if len(heading_stack) < heading_marks:
            heading_stack.extend([""] * (heading_marks - len(heading_stack)))
        heading_stack = heading_stack[:heading_marks]
        heading_stack[-1] = heading_title
        heading_stack = heading_stack[:heading_marks]
        visible_stack = [part for part in heading_stack if part]

        current_path = " > ".join(visible_stack) if visible_stack else fallback_title
        current_title = heading_title
        current_level = heading_marks

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
