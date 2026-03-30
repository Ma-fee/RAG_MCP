from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rag_mcp.models import Chunk, SourceDocument


@dataclass
class _TocNode:
    level: int
    title: str
    heading_path: str
    page_start: int
    page_end: int  # inclusive, 1-based


def _extract_toc_nodes(pdf_path: Path) -> list[_TocNode]:
    """Extract TOC nodes with page ranges from PDF using PyMuPDF."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return []

    doc = fitz.open(str(pdf_path))
    raw_toc = doc.get_toc()  # [(level, title, page), ...]
    total_pages = doc.page_count
    doc.close()

    if not raw_toc:
        return []

    nodes: list[_TocNode] = []
    # ancestor_titles: level -> title, to build heading_path
    ancestor_titles: dict[int, str] = {}

    for i, (level, title, page) in enumerate(raw_toc):
        title = (title or "").strip()
        if not title:
            continue

        # Update ancestor stack
        ancestor_titles[level] = title
        for lvl in list(ancestor_titles):
            if lvl > level:
                del ancestor_titles[lvl]
        heading_path = " > ".join(
            ancestor_titles[lvl] for lvl in sorted(ancestor_titles)
        )

        # Page range: from this node's page to next node's page - 1
        if i + 1 < len(raw_toc):
            next_page = raw_toc[i + 1][2]
            page_end = max(page, next_page - 1)
        else:
            page_end = total_pages

        nodes.append(
            _TocNode(
                level=level,
                title=title,
                heading_path=heading_path,
                page_start=page,
                page_end=page_end,
            )
        )

    return nodes


def _assemble_text(elements: list[Any]) -> str:
    parts: list[str] = []
    for e in elements:
        if e.element_type == "heading":
            parts.append(e.text.strip())
        elif e.element_type in ("text", "list", "code_block"):
            parts.append(e.text.strip())
        elif e.element_type == "table":
            md = e.metadata.get("markdown") or e.text
            if md:
                parts.append(md.strip())
        # image elements are skipped here; CrossReference handles them
    return "\n".join(p for p in parts if p)


class TocAwareChunker:
    """Chunks a PDF document using the PDF's embedded TOC as semantic boundaries.

    One TOC entry = one chunk. Falls back to empty list if the PDF has no
    embedded TOC, allowing the caller to use the default Chunker instead.
    """

    def __init__(self, min_chunk_length: int = 30) -> None:
        self.min_chunk_length = min_chunk_length

    def chunk_document(
        self, document: SourceDocument, pdf_path: Path
    ) -> list[Chunk]:
        nodes = _extract_toc_nodes(pdf_path)
        if not nodes:
            return []

        chunks: list[Chunk] = []
        chunk_index = 0

        for node in nodes:
            node_elements = [
                e
                for e in document.elements
                if node.page_start
                <= e.metadata.get("page_number", 0)
                <= node.page_end
            ]
            text = _assemble_text(node_elements)
            if len(text) < self.min_chunk_length:
                continue

            chunks.append(
                Chunk(
                    chunk_id=f"{document.doc_id}#toc-{chunk_index}",
                    doc_id=document.doc_id,
                    text=text,
                    chunk_index=chunk_index,
                    heading_path=node.heading_path or document.title,
                    section_title=node.title,
                    section_level=node.level,
                    title=document.title,
                    file_type=document.file_type,
                    relative_path=document.relative_path,
                    source_element_ids=[e.element_id for e in node_elements],
                    metadata={
                        "page_start": node.page_start,
                        "page_end": node.page_end,
                        "toc_level": node.level,
                    },
                )
            )
            chunk_index += 1

        return chunks
