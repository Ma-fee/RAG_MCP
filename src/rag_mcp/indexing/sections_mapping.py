from __future__ import annotations

import json
from pathlib import Path

from rag_mcp.chunking.toc_chunker import _extract_toc_nodes
from rag_mcp.indexing.manifest import read_active_manifest
from rag_mcp.ingestion.filesystem import load_supported_documents


def build_sections_mapping(
    data_dir: Path,
    output_path: Path | None = None,
    source_dir: Path | None = None,
    index_dir: Path | None = None,
) -> Path:
    if source_dir is not None and index_dir is not None:
        source_root = source_dir
        target_path = (
            output_path.resolve()
            if output_path
            else index_dir / "sections_mapping.json"
        )
    else:
        data_dir = data_dir.resolve()
        manifest = read_active_manifest(data_dir / "active_index.json")
        if manifest is None:
            raise RuntimeError("active_index.json 不存在，请先执行 rag_rebuild_index")

        src = manifest.get("source_dir")
        if not src:
            raise RuntimeError(
                "active_index.json 缺少 source_dir，请先重新执行 rag_rebuild_index"
            )

        source_root = Path(src)
        idx_dir = Path(manifest["index_dir"])
        target_path = (
            output_path.resolve() if output_path else idx_dir / "sections_mapping.json"
        )

    documents = sorted(
        load_supported_documents(source_root), key=lambda item: item.relative_path
    )

    mapping: dict[str, list[str]] = {}
    for doc in documents:
        key = Path(doc.relative_path).stem
        if not key:
            continue

        sections: list[str] = []

        pdf_path = source_root / doc.relative_path
        if doc.file_type == "pdf" and pdf_path.exists():
            nodes = _extract_toc_nodes(pdf_path)
            for node in nodes:
                title = str(node.title).strip()
                if title and title not in sections:
                    sections.append(title)

        if not sections:
            for element in doc.elements:
                title = str(element.section_title).strip()
                if title and title not in sections:
                    sections.append(title)

        mapping[key] = sections

    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return target_path
