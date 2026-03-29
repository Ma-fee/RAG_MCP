from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from docling.document_converter import DocumentConverter

from rag_mcp.ingestion.document_model import Document, Element

_SKIP_LABELS = {"page_header", "page_footer", "footnote"}
_HEADING_LABELS = {"title", "section_header"}
_TABLE_LABELS = {"table"}
_PICTURE_LABELS = {"picture"}


def parse_document_file(
    path: Path,
    root_dir: Path,
    assets_dir: Path | None = None,
) -> Document:
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
        if assets_dir is None:
            assets_dir = root_dir / "assets" / doc_id
        elements = _parse_pdf_elements(path, title, doc_id, assets_dir)
    else:
        raise ValueError(f"unsupported file type: {file_type}")

    return Document(
        doc_id=doc_id,
        title=title,
        relative_path=relative_path,
        file_type=file_type,
        elements=elements,
    )


def _parse_pdf_elements(
    path: Path,
    title: str,
    doc_id: str,
    assets_dir: Path,
) -> list[Element]:
    converter = DocumentConverter()
    result = converter.convert(str(path))
    dl_doc = result.document

    elements: list[Element] = []
    heading_stack: list[str] = [title]
    image_n = 0

    for item, _level in dl_doc.iterate_items():
        label_val = getattr(item.label, "value", str(item.label))

        if label_val in _SKIP_LABELS:
            continue

        if label_val in _HEADING_LABELS:
            text = getattr(item, "text", "").strip()
            if not text:
                continue
            level = _heading_level(label_val, text)
            # Trim stack to current level and push new heading
            heading_stack = heading_stack[:level]
            heading_stack.append(text)
            elements.append(
                Element(
                    element_id=f"el-{len(elements)}",
                    element_type="heading",
                    text=text,
                    heading_path=" > ".join(heading_stack),
                    section_title=text,
                    section_level=level,
                    metadata=_prov_metadata(item),
                )
            )
            continue

        if label_val in _TABLE_LABELS:
            md = item.export_to_markdown(dl_doc) if hasattr(item, "export_to_markdown") else ""
            caption = _caption_text(item)
            meta: dict[str, Any] = {
                "markdown": md,
                "caption": caption,
                **_prov_metadata(item),
            }
            elements.append(
                Element(
                    element_id=f"el-{len(elements)}",
                    element_type="table",
                    text=md,
                    heading_path=" > ".join(heading_stack),
                    section_title=heading_stack[-1] if heading_stack else title,
                    section_level=len(heading_stack) - 1,
                    metadata=meta,
                )
            )
            continue

        if label_val in _PICTURE_LABELS:
            caption = _caption_text(item)
            img_path = _save_picture(item, dl_doc, assets_dir, image_n)
            image_n += 1
            meta = {
                "caption": caption,
                "image_path": str(img_path) if img_path else "",
                **_prov_metadata(item),
            }
            elements.append(
                Element(
                    element_id=f"el-{len(elements)}",
                    element_type="image",
                    text=caption,
                    heading_path=" > ".join(heading_stack),
                    section_title=heading_stack[-1] if heading_stack else title,
                    section_level=len(heading_stack) - 1,
                    metadata=meta,
                )
            )
            continue

        # Default: text element
        text = getattr(item, "text", "").strip()
        if not text:
            continue
        elements.append(
            Element(
                element_id=f"el-{len(elements)}",
                element_type="text",
                text=text,
                heading_path=" > ".join(heading_stack),
                section_title=heading_stack[-1] if heading_stack else title,
                section_level=max(0, len(heading_stack) - 1),
                metadata=_prov_metadata(item),
            )
        )

    if not elements:
        elements = _single_text_element(text=title, heading_path=title, section_title=title)

    return elements


def _heading_level(label_val: str, text: str) -> int:
    if label_val == "title":
        return 1
    # Heuristic: detect numeric prefix like "1.2.3 "
    import re
    m = re.match(r'^(\d+(?:\.\d+)*)\s', text)
    if m:
        return len(m.group(1).split(".")) + 1
    return 2


def _caption_text(item: Any) -> str:
    captions = getattr(item, "captions", [])
    if captions:
        cap = captions[0]
        return getattr(cap, "text", str(cap)).strip()
    return ""


def _prov_metadata(item: Any) -> dict[str, Any]:
    prov = getattr(item, "prov", [])
    if prov:
        return {"page_number": prov[0].page_no}
    return {"page_number": 0}


def _save_picture(
    item: Any,
    dl_doc: Any,
    assets_dir: Path,
    image_n: int,
) -> Path | None:
    try:
        pil_img = item.get_image(dl_doc)
        if pil_img is None:
            return None
        assets_dir.mkdir(parents=True, exist_ok=True)
        img_path = assets_dir / f"image-{image_n}.png"
        pil_img.save(img_path)
        return img_path
    except Exception:
        return None


# ── Markdown / TXT helpers (unchanged) ──────────────────────────────────────

def _single_text_element(text: str, heading_path: str, section_title: str) -> list[Element]:
    cleaned = text.strip()
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
    import re
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
        text_buffer.clear()

    for line in text.splitlines():
        stripped = line.strip()
        m = re.match(r'^(#{1,6})\s+(.*)', stripped)
        if m:
            flush_text()
            level = len(m.group(1))
            heading = m.group(2).strip()
            heading_stack = heading_stack[: level - 1]
            heading_stack.append(heading)
            section_title = heading
            section_level = level
            heading_path = " > ".join(heading_stack) if heading_stack else title
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
