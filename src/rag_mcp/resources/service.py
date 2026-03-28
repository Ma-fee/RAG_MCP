from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rag_mcp.errors import ErrorCode, ServiceError, ServiceException
from rag_mcp.indexing.manifest import read_active_manifest
from rag_mcp.resources.uri import parse_rag_uri


class ResourceService:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = Path(data_dir)

    def read(self, uri: str) -> dict[str, Any]:
        parsed = parse_rag_uri(uri)
        manifest = read_active_manifest(self.data_dir / "active_index.json")
        if manifest is None:
            raise ServiceException(
                ServiceError(
                    code=ErrorCode.NO_ACTIVE_INDEX,
                    message="当前没有活动索引",
                    hint="请先调用 rag_rebuild_index",
                )
            )
        if manifest["corpus_id"] != parsed.corpus_id:
            raise ServiceException(
                ServiceError(
                    code=ErrorCode.RESOURCE_NOT_FOUND,
                    message="资源不在当前活动索引中",
                    hint="请确认 rag:// URI 与活动索引匹配",
                )
            )

        store = json.loads(
            (Path(manifest["index_dir"]) / "keyword_store.json").read_text(
                encoding="utf-8"
            )
        )
        for entry in store["entries"]:
            if entry["uri"] == uri:
                return {
                    "uri": entry["uri"],
                    "text": entry["text"],
                    "metadata": entry["metadata"],
                }

        raise ServiceException(
            ServiceError(
                code=ErrorCode.RESOURCE_NOT_FOUND,
                message="未找到对应资源",
                hint="请确认 uri 来源于最新检索结果",
            )
        )

