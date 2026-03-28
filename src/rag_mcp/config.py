from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    data_dir: Path
    enable_http: bool
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

    @classmethod
    def from_env(cls) -> "AppConfig":
        return cls(
            data_dir=Path(os.getenv("RAG_MCP_DATA_DIR", ".rag_mcp_data")),
            enable_http=_to_bool(os.getenv("ENABLE_HTTP", "false")),
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
        )


def _to_optional_int(value: str | None) -> int | None:
    if value is None or value.strip() == "":
        return None
    return int(value)


def _to_bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}
