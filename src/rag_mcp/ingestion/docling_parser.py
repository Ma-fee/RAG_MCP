from __future__ import annotations

import hashlib
import re
from pathlib import Path

from rag_mcp.ingestion.document_model import Document, Element


def parse_document_file(path: Path, root_dir: Path) -> Document:
    relative_path = path.relative_to(root_dir).as_posix()
    file_type = path.suffix.lower().lstrip(".")
    doc_id = hashlib.sha1(relative_path.encode("utf-8")).hexdigest()[:16]
    title = path.name

    if file_type == "md":
        elements = _parse_markdown_elements(path.read_text(encoding="utf-8"), title)
    elif file_type == "txt":
        text = path.read_text(encoding="utf-8")
        elements = _single_text_element(text=text, heading_path=title, section_title=title)
    elif file_type == "pdf":
        text = _extract_pdf_text(path)
        elements = _single_text_element(text=text, heading_path=title, section_title=title)
    else:
        raise ValueError(f"unsupported file type: {file_type}")

    return Document(
        doc_id=doc_id,
        title=title,
        relative_path=relative_path,
        file_type=file_type,
        elements=elements,
    )


def _single_text_element(text: str, heading_path: str, section_title: str) -> list[Element]:
    cleaned = " ".join(text.split()).strip()
    if not cleaned:
        cleaned = section_title
    return [
        Element(
            element_id="el-0",
            element_type="text",
            text=cleaned,
            heading_path=heading_path,
            section_title=section_title,
            section_level=0,
        )
    ]


def _parse_markdown_elements(text: str, title: str) -> list[Element]:
    elements: list[Element] = []
    heading_stack: list[str] = []
    section_title = title
    section_level = 0
    heading_path = title
    text_buffer: list[str] = []

    def flush_text() -> None:
        nonlocal text_buffer
        cleaned = " ".join(" ".join(text_buffer).split()).strip()
        if cleaned:
            elements.append(
                Element(
                    element_id=f"el-{len(elements)}",
                    element_type="text",
                    text=cleaned,
                    heading_path=heading_path,
                    section_title=section_title,
                    section_level=section_level,
                )
            )
        text_buffer = []

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            flush_text()
            continue
        if stripped.startswith("#"):
            marks = len(stripped) - len(stripped.lstrip("#"))
            if 1 <= marks <= 6 and (len(stripped) == marks or stripped[marks] == " "):
                flush_text()
                heading = stripped[marks:].strip() or title
                if len(heading_stack) < marks:
                    heading_stack.extend([""] * (marks - len(heading_stack)))
                heading_stack = heading_stack[:marks]
                heading_stack[-1] = heading
                visible = [part for part in heading_stack if part]
                heading_path = " > ".join(visible) if visible else title
                section_title = heading
                section_level = marks
                elements.append(
                    Element(
                        element_id=f"el-{len(elements)}",
                        element_type="heading",
                        text=heading,
                        heading_path=heading_path,
                        section_title=section_title,
                        section_level=section_level,
                    )
                )
                continue
        text_buffer.append(stripped)

    flush_text()
    if not elements:
        return _single_text_element(text=text, heading_path=title, section_title=title)
    return elements


def _extract_pdf_text(path: Path) -> str:
    raw = path.read_bytes()
    try:
        decoded = raw.decode("utf-8")
    except UnicodeDecodeError:
        decoded = raw.decode("latin-1", errors="ignore")

    # Very lightweight text extraction fallback for fixtures and simple PDFs.
    matches = re.findall(r"\(([^()]*)\)\s*Tj", decoded)
    if matches:
        return " ".join(matches)
    return " ".join(decoded.split())
