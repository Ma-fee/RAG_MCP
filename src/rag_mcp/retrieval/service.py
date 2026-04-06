from __future__ import annotations

from pathlib import Path
from typing import Any

from rag_mcp.errors import ErrorCode, ServiceError, ServiceException
from rag_mcp.indexing.keyword_index import KeywordIndex
from rag_mcp.indexing.repositories import (
    ActiveIndexRepository,
    RepositoryFormatError,
    RepositoryNotFoundError,
)
from rag_mcp.retrieval.models import SearchHit


class RetrievalService:
    def __init__(
        self,
        data_dir: Path,
        embedding_provider: Any | None = None,
        reranker: Any | None = None,
        rerank_top_k_candidates: int = 20,
    ) -> None:
        self.data_dir = Path(data_dir)
        self._reranker = reranker
        self._rerank_top_k_candidates = rerank_top_k_candidates
        self.active_indexes = ActiveIndexRepository(self.data_dir)

    def search(
        self,
        query: str,
        top_k: int = 5,
        mode: str | None = None,
    ) -> dict[str, Any]:
        # Unified search entry: always use rerank pipeline on the new index chain.
        return self._search_rerank(query=query, top_k=top_k)

    def _search_keyword(self, query: str, top_k: int) -> dict[str, Any]:
        manifest = self._load_active_manifest()
        keyword_index = KeywordIndex.load(Path(manifest["index_dir"]))
        raw_hits = keyword_index.search(query, top_k=top_k)
        results = [
            SearchHit(
                uri=hit["uri"],
                text=hit["text"],
                title=hit["title"],
                score=hit["score"],
                metadata=hit["metadata"],
            ).to_dict()
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

    def _search_rerank(self, query: str, top_k: int) -> dict[str, Any]:
        candidates = self._search_keyword(
            query=query,
            top_k=self._rerank_top_k_candidates,
        )["results"]
        if self._reranker is None:
            results = candidates[:top_k]
        else:
            reranked = self._reranker.rerank(query=query, candidates=candidates)
            results = reranked[:top_k]
        return {
            "query": query,
            "mode": "rerank",
            "top_k": top_k,
            "result_count": len(results),
            "results": results,
        }


def read_active_manifest(manifest_path: Path) -> dict[str, Any] | None:
    try:
        return ActiveIndexRepository(Path(manifest_path).parent).load()
    except (RepositoryNotFoundError, RepositoryFormatError):
        return None
