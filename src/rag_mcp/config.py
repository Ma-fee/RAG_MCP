from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    data_dir: Path
    http_host: str
    http_port: int
    embedding_api_key: str
    embedding_base_url: str
    embedding_model: str
    embedding_dimension: int | None
    embedding_timeout_seconds: int
    default_top_k: int
    keyword_top_k: int
    chunk_size: int
    chunk_overlap: int
    multimodal_api_key: str
    multimodal_base_url: str
    multimodal_model: str
    mcp_transport: str
    rerank_api_key: str
    rerank_base_url: str
    rerank_model: str
    rerank_timeout_seconds: int
    rerank_top_k_candidates: int

    @classmethod
    def from_env(cls) -> "AppConfig":
        return cls(
            data_dir=Path(os.getenv("RAG_MCP_DATA_DIR", ".rag_mcp_data")),
            http_host=os.getenv("HTTP_HOST", "127.0.0.1"),
            http_port=int(os.getenv("HTTP_PORT", "8787")),
            embedding_api_key=os.getenv("EMBEDDING_API_KEY", ""),
            embedding_base_url=os.getenv(
                "EMBEDDING_BASE_URL", "https://api.siliconflow.cn/v1"
            ),
            embedding_model=os.getenv(
                "EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-0.6B"
            ),
            embedding_dimension=_to_optional_int(os.getenv("EMBEDDING_DIMENSION")),
            embedding_timeout_seconds=int(
                os.getenv("EMBEDDING_TIMEOUT_SECONDS", "30")
            ),
            default_top_k=int(os.getenv("DEFAULT_TOP_K", "5")),
            keyword_top_k=int(os.getenv("KEYWORD_TOP_K", "8")),
            chunk_size=int(os.getenv("CHUNK_SIZE", "800")),
            chunk_overlap=int(os.getenv("CHUNK_OVERLAP", "120")),
            multimodal_api_key=os.getenv("MULTIMODAL_API_KEY", ""),
            multimodal_base_url=os.getenv("MULTIMODAL_BASE_URL", "https://api.siliconflow.cn/v1"),
            multimodal_model=os.getenv("MULTIMODAL_MODEL", "zai-org/GLM-4.6V"),
            mcp_transport=os.getenv("MCP_TRANSPORT", "stdio"),
            rerank_api_key=os.getenv("RERANK_API_KEY", ""),
            rerank_base_url=os.getenv("RERANK_BASE_URL", "https://api.siliconflow.cn/v1"),
            rerank_model=os.getenv("RERANK_MODEL", "Qwen/Qwen3-Reranker-0.6B"),
            rerank_timeout_seconds=int(os.getenv("RERANK_TIMEOUT_SECONDS", "30")),
            rerank_top_k_candidates=int(os.getenv("RERANK_TOP_K_CANDIDATES", "20")),
        )


def _to_optional_int(value: str | None) -> int | None:
    if value is None or value.strip() == "":
        return None
    return int(value)
