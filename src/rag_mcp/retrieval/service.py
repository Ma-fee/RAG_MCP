from __future__ import annotations

from pathlib import Path
from typing import Any

from rag_mcp.errors import ErrorCode, ServiceError, ServiceException
from rag_mcp.indexing.keyword_index import KeywordIndex
from rag_mcp.indexing.manifest import read_active_manifest
from rag_mcp.indexing.vector_index import VectorIndex


class RetrievalService:
    def __init__(self, data_dir: Path, embedding_provider: Any | None = None) -> None:
        self.data_dir = Path(data_dir)
        self.embedding_provider = embedding_provider

    def search(self, query: str, mode: str, top_k: int = 5) -> dict[str, Any]:
        if mode == "keyword":
            return self._search_keyword(query=query, top_k=top_k)
        if mode == "vector":
            return self._search_vector(query=query, top_k=top_k)
        if mode in {"hybrid", "rerank"}:
            raise ServiceException(
                ServiceError(
                    code=ErrorCode.SEARCH_MODE_NOT_IMPLEMENTED,
                    message=f"检索模式尚未实现: {mode}",
                    hint="当前版本仅支持 keyword/vector",
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

    def _search_vector(self, query: str, top_k: int) -> dict[str, Any]:
        manifest = self._load_active_manifest()
        self._validate_vector_config_or_raise(manifest)
        if self.embedding_provider is None:
            raise ServiceException(
                ServiceError(
                    code=ErrorCode.SEARCH_MODE_NOT_IMPLEMENTED,
                    message="vector 检索缺少 embedding provider",
                    hint="请配置 EmbeddingProvider 后再执行 vector 检索",
                )
            )

        vector_index = VectorIndex(index_dir=Path(manifest["index_dir"]))
        query_embedding = self.embedding_provider.embed_query(query)
        raw_hits = vector_index.search_by_vector(query_embedding, top_k=top_k)
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
            "mode": "vector",
            "top_k": top_k,
            "result_count": len(results),
            "results": results,
        }

    def _validate_vector_config_or_raise(self, manifest: dict[str, Any]) -> None:
        if self.embedding_provider is None:
            return
        expected_model = manifest.get("embedding_model")
        expected_dimension = manifest.get("embedding_dimension")
        actual_model = self.embedding_provider.model_name()
        actual_dimension = self.embedding_provider.embedding_dimension()

        if (
            expected_model is not None
            and expected_dimension is not None
            and (
                str(expected_model) != str(actual_model)
                or int(expected_dimension) != int(actual_dimension)
            )
        ):
            raise ServiceException(
                ServiceError(
                    code=ErrorCode.VECTOR_INDEX_CONFIG_MISMATCH,
                    message=(
                        "活动索引 embedding 配置与当前运行配置不一致"
                    ),
                    hint="请重新执行 rag_rebuild_index 以重建向量索引",
                    details={
                        "index_embedding_model": str(expected_model),
                        "runtime_embedding_model": str(actual_model),
                        "index_embedding_dimension": str(expected_dimension),
                        "runtime_embedding_dimension": str(actual_dimension),
                    },
                )
            )
