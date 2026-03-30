from __future__ import annotations

import logging
import sys
from typing import Any

from dotenv import load_dotenv

# 在导入 config 之前加载 .env 文件
load_dotenv()

from rag_mcp.config import AppConfig
from rag_mcp.embedding.client import EmbeddingClient
from rag_mcp.ingestion.vlm_client import VlmClient
from rag_mcp.retrieval.reranker import build_reranker
from rag_mcp.transport.handlers import ToolHandlers
from rag_mcp.transport.mcp_server import create_mcp_server

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger(__name__)


def _build_embedding_provider(cfg: AppConfig) -> Any | None:
    if not cfg.embedding_api_key.strip():
        return None
    return EmbeddingClient.from_config(cfg)


def main() -> None:
    logger.info("Starting RAG MCP server...")
    cfg = AppConfig.from_env()
    embedding_provider = _build_embedding_provider(cfg)
    vlm_client = VlmClient.from_config(cfg)
    reranker = build_reranker(cfg)
    handlers = ToolHandlers(
        cfg.data_dir,
        embedding_provider,
        vlm_client,
        reranker=reranker,
        rerank_top_k_candidates=cfg.rerank_top_k_candidates,
    )
    mcp = create_mcp_server(handlers)

    if cfg.mcp_transport == "sse":
        logger.info(f"Starting SSE server on {cfg.http_host}:{cfg.http_port}")
        mcp.run(
            transport="sse",
            host=cfg.http_host,
            port=cfg.http_port,
        )
    elif cfg.mcp_transport == "streamable-http" or cfg.mcp_transport == "streamable_http":
        logger.info(f"Starting Streamable-HTTP server on {cfg.http_host}:{cfg.http_port}")
        mcp.run(
            transport="streamable-http",
            host=cfg.http_host,
            port=cfg.http_port,
        )
    else:
        logger.info("Starting stdio server")
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
