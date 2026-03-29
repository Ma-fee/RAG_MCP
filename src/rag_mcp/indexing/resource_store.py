from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rag_mcp.ingestion.document_model import Document


@dataclass
class ResourceStore:
    index_dir: Path
    corpus_id: str
    vlm_client: Any  # VlmClient | None

    @property
    def _store_path(self) -> Path:
        return self.index_dir / "resource_store.json"

    def build(self, document: Document) -> list[dict]:
        entries: list[dict] = []
        text_n = image_n = table_n = 0
        for element in document.elements:
            if element.element_type == "text":
                entries.append(self._text_entry(element, document, text_n))
                text_n += 1
            elif element.element_type == "image":
                desc = (
                    self.vlm_client.describe_image(Path(element.metadata["image_path"]))
                    if self.vlm_client
                    else ""
                )
                entries.append(self._image_entry(element, document, image_n, desc))
                image_n += 1
            elif element.element_type == "table":
                entries.append(self._table_entry(element, document, table_n))
                table_n += 1
        self._persist(entries)
        return entries

    def get(self, uri: str) -> dict | None:
        if not self._store_path.exists():
            return None
        data = json.loads(self._store_path.read_text(encoding="utf-8"))
        return next((e for e in data["entries"] if e["uri"] == uri), None)

    def _text_entry(self, element: Any, document: Document, n: int) -> dict:
        return {
            "uri": f"rag://corpus/{self.corpus_id}/{document.doc_id}#text-{n}",
            "type": "text",
            "doc_id": document.doc_id,
            "element_id": element.element_id,
            "text": element.text,
            "heading_path": element.heading_path,
            "section_title": element.section_title,
            "section_level": element.section_level,
            "related": [],
        }

    def _image_entry(self, element: Any, document: Document, n: int, vlm_description: str) -> dict:
        return {
            "uri": f"rag://corpus/{self.corpus_id}/{document.doc_id}#image-{n}",
            "type": "image",
            "doc_id": document.doc_id,
            "element_id": element.element_id,
            "image_path": element.metadata.get("image_path", ""),
            "caption": element.metadata.get("caption", ""),
            "page_number": element.metadata.get("page_number"),
            "vlm_description": vlm_description,
            "related": [],
        }

    def _table_entry(self, element: Any, document: Document, n: int) -> dict:
        return {
            "uri": f"rag://corpus/{self.corpus_id}/{document.doc_id}#table-{n}",
            "type": "table",
            "doc_id": document.doc_id,
            "element_id": element.element_id,
            "markdown": element.metadata.get("markdown", ""),
            "data_json": element.metadata.get("data_json", ""),
            "caption": element.metadata.get("caption", ""),
            "page_number": element.metadata.get("page_number"),
            "related": [],
        }

    def _persist(self, entries: list[dict]) -> None:
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self._store_path.write_text(
            json.dumps({"entries": entries}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
