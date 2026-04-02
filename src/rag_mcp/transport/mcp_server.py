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
    def rag_search(query: str, top_k: int = 5) -> dict:
        return handlers.search(query=query, top_k=top_k)

    @mcp.tool()
    def rag_read_resource(uri: str) -> dict:
        return handlers.read_resource(uri=uri)

    @mcp.tool()
    def rag_list_filenames() -> dict:
        return handlers.list_filenames()

    @mcp.tool()
    def rag_list_sections(filename: str) -> dict:
        return handlers.list_sections(filename=filename)

    @mcp.tool()
    def rag_section_retrieval(
        title: list[str],
        filename: str,
        description: str = "",
        top_k: int = 10,
    ) -> dict:
        return handlers.section_retrieval(
            title=title,
            filename=filename,
            description=description,
            top_k=top_k,
        )

    @mcp.resource("rag://corpus/{corpus_id}/{doc_id}#{fragment}")
    def rag_resource(corpus_id: str, doc_id: str, fragment: str) -> dict:
        uri = f"rag://corpus/{corpus_id}/{doc_id}#{fragment}"
        return handlers.read_resource(uri=uri)

    return mcp
