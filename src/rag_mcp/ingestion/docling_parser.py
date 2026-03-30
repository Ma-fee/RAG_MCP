from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from docling.datamodel.document import DoclingDocument
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.utils.model_downloader import download_models

from rag_mcp.ingestion.document_model import Document, Element

logger = logging.getLogger(__name__)

# 模型存放在项目根目录下，避免散落到 ~/.cache
_MODELS_DIR = Path(__file__).resolve().parents[3] / ".docling_models"
_DOCLING_CACHE_DIR = Path(__file__).resolve().parents[3] / ".docling_cache"

class _Label:
    SKIP    = frozenset({"page_header", "page_footer", "footnote", "caption", "document_index"})
    HEADING = frozenset({"title", "section_header"})
    TABLE   = frozenset({"table"})
    PICTURE = frozenset({"picture"})

_ELEMENT_CACHE_VERSION  = "2"  # bump when parse/filter logic changes
_PIPELINE_VERSION       = "2"  # bump when PdfPipelineOptions change


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


def _ensure_models() -> Path:
    models_dir = _MODELS_DIR
    layout_model = models_dir / "docling-project--docling-layout-heron" / "model.safetensors"
    if not layout_model.exists():
        download_models(output_dir=models_dir, progress=True)
    return models_dir


def _load_dl_doc(path: Path) -> DoclingDocument:
    _DOCLING_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    mtime = int(path.stat().st_mtime)
    key = hashlib.sha1(str(path.resolve()).encode()).hexdigest()[:16] + f"_{mtime}_p{_PIPELINE_VERSION}"
    cache_file = _DOCLING_CACHE_DIR / f"{key}.json"
    if cache_file.exists():
        logger.debug("DoclingDocument cache hit: %s", path.name)
        return DoclingDocument.model_validate_json(cache_file.read_text(encoding="utf-8"))
    models_dir = _ensure_models()
    pipeline_opts = PdfPipelineOptions(
        artifacts_path=models_dir,
        generate_picture_images=True,
    )
    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_opts)}
    )
    dl_doc = converter.convert(str(path)).document
    json_str = dl_doc.model_dump_json()
    if isinstance(json_str, str):
        cache_file.write_text(json_str, encoding="utf-8")
    logger.debug("DoclingDocument cached: %s", path.name)
    return dl_doc


def _parse_pdf_elements(
    path: Path,
    title: str,
    doc_id: str,
    assets_dir: Path,
) -> list[Element]:
    dl_doc = _load_dl_doc(path)

    elements: list[Element] = []
    heading_stack: list[str] = [title]
    image_n = 0

    for item, _level in dl_doc.iterate_items():
        label_val = getattr(item.label, "value", str(item.label))

        if label_val in _Label.SKIP:
            continue

        if label_val in _Label.HEADING:
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

        if label_val in _Label.TABLE:
            if label_val == "document_index":
                continue
            md = item.export_to_markdown(dl_doc) if hasattr(item, "export_to_markdown") else ""
            caption = _caption_text(item, dl_doc)
            meta: dict[str, Any] = {
                "markdown": md,
                "caption": caption,
                "data_json": _table_data_json(item),
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

        if label_val in _Label.PICTURE:
            caption = _caption_text(item, dl_doc)
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


def _table_data_json(item: Any) -> list[dict]:
    data = getattr(item, "data", None)
    if not data:
        return []
    grid = getattr(data, "grid", None)
    if not grid:
        return []
    header_row = grid[0]
    if any(getattr(cell, "column_header", False) for cell in header_row):
        headers = [getattr(cell, "text", "").strip() for cell in header_row]
        data_start = 1
    else:
        headers = [f"col_{i}" for i in range(len(header_row))]
        data_start = 0
    rows = []
    for row in grid[data_start:]:
        rows.append({
            (headers[i] if i < len(headers) else str(i)): getattr(cell, "text", "").strip()
            for i, cell in enumerate(row)
        })
    return rows


def _caption_text(item: Any, dl_doc: Any) -> str:
    captions = getattr(item, "captions", [])
    if not captions:
        return ""
    ref = captions[0]
    cref = getattr(ref, "cref", None)
    if cref and cref.startswith("#/texts/"):
        idx = int(cref.split("/")[-1])
        texts = getattr(dl_doc, "texts", [])
        if idx < len(texts):
            return getattr(texts[idx], "text", "").strip()
    return getattr(ref, "text", "").strip()


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
        img_obj = getattr(item, "image", None)
        pil_img = getattr(img_obj, "pil_image", None) if img_obj is not None else None
        if pil_img is None:
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


# ── Element-level cache ──────────────────────────────────────────────────────

_ELEMENT_CACHE_DIR = Path(__file__).resolve().parents[3] / ".element_cache"


def parse_document_file_cached(
    path: Path,
    root_dir: Path,
    assets_dir: Path | None = None,
    cache_dir: Path | None = None,
) -> Document:
    """Like parse_document_file but caches the resulting Document as JSON."""
    resolved = path.resolve()
    mtime = int(resolved.stat().st_mtime)
    key = (
        hashlib.sha1(str(resolved).encode()).hexdigest()[:16]
        + f"_{mtime}_{_ELEMENT_CACHE_VERSION}"
    )
    cache_root = cache_dir or _ELEMENT_CACHE_DIR
    cache_root.mkdir(parents=True, exist_ok=True)
    cache_file = cache_root / f"{key}.json"

    if cache_file.exists():
        logger.debug("Element cache hit: %s", path.name)
        raw = json.loads(cache_file.read_text(encoding="utf-8"))
        elements = [
            Element(
                element_id=e["element_id"],
                element_type=e["element_type"],
                text=e["text"],
                heading_path=e["heading_path"],
                section_title=e["section_title"],
                section_level=e["section_level"],
                metadata=e.get("metadata", {}),
            )
            for e in raw["elements"]
        ]
        return Document(
            doc_id=raw["doc_id"],
            title=raw["title"],
            relative_path=raw["relative_path"],
            file_type=raw["file_type"],
            elements=elements,
        )

    doc = parse_document_file(path, root_dir, assets_dir=assets_dir)
    payload = dataclasses.asdict(doc)
    cache_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    logger.debug("Element cache written: %s", path.name)
    return doc
