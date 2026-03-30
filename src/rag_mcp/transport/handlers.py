from __future__ import annotations

from pathlib import Path
from typing import Any

from rag_mcp.errors import ServiceException
from rag_mcp.ingestion.filesystem import load_supported_documents
from rag_mcp.indexing.manifest import read_active_manifest
from rag_mcp.indexing.rebuild import rebuild_keyword_index
from rag_mcp.resources.service import ResourceService
from rag_mcp.retrieval.service import RetrievalService


class ToolHandlers:
    def __init__(
        self,
        data_dir: Path,
        embedding_provider: Any | None = None,
        vlm_client: Any | None = None,
        reranker: Any | None = None,
        rerank_top_k_candidates: int = 20,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.embedding_provider = embedding_provider
        self.vlm_client = vlm_client
        self.retrieval = RetrievalService(
            self.data_dir,
            embedding_provider=self.embedding_provider,
            reranker=reranker,
            rerank_top_k_candidates=rerank_top_k_candidates,
        )
        self.resources = ResourceService(self.data_dir)

    def rebuild_index(self, directory_path: str) -> dict:
        source_dir = Path(directory_path)
        if not source_dir.exists() or not source_dir.is_dir():
            return {"error": "invalid_directory", "message": "目录不存在或路径无效"}
        if not load_supported_documents(source_dir):
            return {"error": "no_documents", "message": "目录中没有可索引文档"}
        try:
            result = rebuild_keyword_index(
                source_dir=source_dir,
                data_dir=self.data_dir,
                embedding_provider=self.embedding_provider,
                vlm_client=self.vlm_client,
            )
            return {
                "corpus_id": result["corpus_id"],
                "source_directory": directory_path,
                "document_count": result["document_count"],
                "chunk_count": result["chunk_count"],
                "indexed_at": result["indexed_at"],
            }
        except Exception as exc:
            return {"error": "rebuild_failed", "message": str(exc)}

    def index_status(self) -> dict:
        manifest = read_active_manifest(self.data_dir / "active_index.json")
        if manifest is None:
            return {"has_active_index": False}
        return {
            "has_active_index": True,
            "corpus_id": manifest["corpus_id"],
            "document_count": manifest["document_count"],
            "chunk_count": manifest["chunk_count"],
            "indexed_at": manifest["indexed_at"],
        }

    def search(self, query: str, mode: str, top_k: int = 5) -> dict:
        try:
            return self.retrieval.search(query=query, mode=mode, top_k=top_k)
        except ServiceException as exc:
            return {"error": exc.error.code.value, "message": exc.error.message}

    def read_resource(self, uri: str) -> dict:
        try:
            return self.resources.read(uri)
        except ServiceException as exc:
            return {"error": exc.error.code.value, "message": exc.error.message}
