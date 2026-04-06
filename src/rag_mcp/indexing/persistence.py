from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from rag_mcp.indexing.keyword_index import persist_keyword_store
from rag_mcp.indexing.manifest import write_active_manifest_atomic


class IndexPersistenceService:
    def __init__(self, *, data_dir: Path, index_dir: Path) -> None:
        self.data_dir = Path(data_dir)
        self.index_dir = Path(index_dir)

    def write_keyword_store(self, *, corpus_id: str, entries: list[dict[str, Any]]) -> None:
        persist_keyword_store(index_dir=self.index_dir, corpus_id=corpus_id, entries=entries)

    def write_resource_store(self, *, entries: list[dict[str, Any]]) -> None:
        self.index_dir.mkdir(parents=True, exist_ok=True)
        (self.index_dir / "resource_store.json").write_text(
            json.dumps({"entries": entries}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def write_active_manifest(self, payload: dict[str, Any]) -> None:
        write_active_manifest_atomic(self.data_dir / "active_index.json", payload)

    def remove_index_dir(self, index_dir: Path) -> None:
        path = Path(index_dir)
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
