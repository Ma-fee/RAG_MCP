from __future__ import annotations

from pathlib import Path
from typing import Any

from rag_mcp.errors import ErrorCode, ServiceError, ServiceException
from rag_mcp.indexing.keyword_index import KeywordIndex
from rag_mcp.indexing.manifest import read_active_manifest


class RetrievalService:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = Path(data_dir)

    def search(self, query: str, mode: str, top_k: int = 5) -> dict[str, Any]:
        if mode == "keyword":
            return self._search_keyword(query=query, top_k=top_k)
        if mode in {"vector", "hybrid", "rerank"}:
            raise ServiceException(
                ServiceError(
                    code=ErrorCode.SEARCH_MODE_NOT_IMPLEMENTED,
                    message=f"检索模式尚未实现: {mode}",
                    hint="Phase 1 仅支持 keyword 检索",
                )
            )
        raise ServiceException(
            ServiceError(
                code=ErrorCode.UNSUPPORTED_SEARCH_MODE,
                message=f"不支持的检索模式: {mode}",
                hint="请使用 keyword 或等待后续版本",
            )
        )

    def _search_keyword(self, query: str, top_k: int) -> dict[str, Any]:
        manifest = self._load_active_manifest()
        keyword_index = KeywordIndex.load(Path(manifest["index_dir"]))
        raw_hits = keyword_index.search(query, top_k=top_k)
        results = [
            {
                "text": hit["text"],
                "title": hit["title"],
                "uri": hit["uri"],
                "score": hit["score"],
                "metadata": hit["metadata"],
            }
            for hit in raw_hits
        ]
        return {
            "query": query,
            "mode": "keyword",
            "top_k": top_k,
            "result_count": len(results),
            "results": results,
        }

    def _load_active_manifest(self) -> dict[str, Any]:
        manifest = read_active_manifest(self.data_dir / "active_index.json")
        if manifest is None:
            raise ServiceException(
                ServiceError(
                    code=ErrorCode.NO_ACTIVE_INDEX,
                    message="当前没有活动索引",
                    hint="请先调用 rag_rebuild_index",
                )
            )
        return manifest

