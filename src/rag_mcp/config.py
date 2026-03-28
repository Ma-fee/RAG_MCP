from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    data_dir: Path
    embedding_base_url: str
    embedding_model: str
    default_top_k: int
    keyword_top_k: int
    chunk_size: int
    chunk_overlap: int

    @classmethod
    def from_env(cls) -> "AppConfig":
        return cls(
            data_dir=Path(os.getenv("RAG_MCP_DATA_DIR", ".rag_mcp_data")),
            embedding_base_url=os.getenv(
                "EMBEDDING_BASE_URL", "https://api.siliconflow.cn/v1"
            ),
            embedding_model=os.getenv(
                "EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-0.6B"
            ),
            default_top_k=int(os.getenv("DEFAULT_TOP_K", "5")),
            keyword_top_k=int(os.getenv("KEYWORD_TOP_K", "8")),
            chunk_size=int(os.getenv("CHUNK_SIZE", "800")),
            chunk_overlap=int(os.getenv("CHUNK_OVERLAP", "120")),
        )

