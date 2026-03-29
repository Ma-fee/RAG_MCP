from __future__ import annotations

from typing import Any

import fastmcp


def create_mcp_server(handlers: Any) -> fastmcp.FastMCP:
    mcp = fastmcp.FastMCP("rag-mcp")

    @mcp.tool()
    def rag_rebuild_index(directory_path: str) -> dict:
        return handlers.rebuild_index(directory_path)

    @mcp.tool()
    def rag_index_status() -> dict:
        return handlers.index_status()

    @mcp.tool()
    def rag_search(query: str, mode: str = "keyword", top_k: int = 5) -> dict:
        return handlers.search(query=query, mode=mode, top_k=top_k)

    @mcp.tool()
    def rag_read_resource(uri: str) -> dict:
        return handlers.read_resource(uri=uri)

    return mcp
