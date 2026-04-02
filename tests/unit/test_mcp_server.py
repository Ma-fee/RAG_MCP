from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from rag_mcp.transport.mcp_server import create_mcp_server


def _make_handlers() -> MagicMock:
    h = MagicMock()
    h.rebuild_index.return_value = {"corpus_id": "abc", "chunk_count": 1, "document_count": 1}
    h.index_status.return_value = {"has_active_index": False}
    h.search.return_value = {"mode": "keyword", "result_count": 0, "results": []}
    h.read_resource.return_value = {"uri": "rag://corpus/c/d#text-0", "type": "text", "text": "hello"}
    h.list_filenames.return_value = {"count": 1, "filenames": [{"filename": "doc", "relative_path": "doc.pdf", "file_type": "pdf", "chunk_count": 3}]}
    h.list_sections.return_value = {"filename": "doc", "section_count": 1, "sections": [{"title": "1 前言"}]}
    h.section_retrieval.return_value = {"result_count": 1, "results": [{"uri": "rag://corpus/c/d#text-0", "title": "1 前言", "text": "..."}]}
    return h


def test_mcp_server_registers_four_tools() -> None:
    handlers = _make_handlers()
    mcp = create_mcp_server(handlers)
    tools = mcp.list_tools()
    # list_tools may be sync or async depending on version; handle both
    import inspect
    if inspect.iscoroutine(tools):
        import asyncio
        tools = asyncio.get_event_loop().run_until_complete(tools)
    tool_names = {t.name for t in tools}
    assert "rag_rebuild_index" in tool_names
    assert "rag_search" in tool_names
    assert "rag_read_resource" in tool_names
    assert "rag_index_status" in tool_names
    assert "rag_list_filenames" in tool_names
    assert "rag_list_sections" in tool_names
    assert "rag_section_retrieval" in tool_names


@pytest.mark.asyncio
async def test_mcp_server_rebuild_calls_handler() -> None:
    handlers = _make_handlers()
    mcp = create_mcp_server(handlers)
    result = await mcp.call_tool("rag_rebuild_index", {"directory_path": "/tmp"})
    handlers.rebuild_index.assert_called_once_with("/tmp")
    assert result is not None


@pytest.mark.asyncio
async def test_mcp_server_search_calls_handler() -> None:
    handlers = _make_handlers()
    mcp = create_mcp_server(handlers)
    await mcp.call_tool("rag_search", {"query": "hello", "top_k": 3})
    handlers.search.assert_called_once_with(query="hello", top_k=3)


@pytest.mark.asyncio
async def test_mcp_server_read_resource_calls_handler() -> None:
    handlers = _make_handlers()
    mcp = create_mcp_server(handlers)
    await mcp.call_tool("rag_read_resource", {"uri": "rag://corpus/c/d#text-0"})
    handlers.read_resource.assert_called_once_with(uri="rag://corpus/c/d#text-0")


@pytest.mark.asyncio
async def test_mcp_server_list_filenames_calls_handler() -> None:
    handlers = _make_handlers()
    mcp = create_mcp_server(handlers)
    await mcp.call_tool("rag_list_filenames", {})
    handlers.list_filenames.assert_called_once_with()


@pytest.mark.asyncio
async def test_mcp_server_list_sections_calls_handler() -> None:
    handlers = _make_handlers()
    mcp = create_mcp_server(handlers)
    await mcp.call_tool("rag_list_sections", {"filename": "doc"})
    handlers.list_sections.assert_called_once_with(filename="doc")


@pytest.mark.asyncio
async def test_mcp_server_section_retrieval_calls_handler() -> None:
    handlers = _make_handlers()
    mcp = create_mcp_server(handlers)
    await mcp.call_tool(
        "rag_section_retrieval",
        {
            "title": ["1 前言"],
            "filename": "doc",
            "description": "前言",
            "top_k": 2,
        },
    )
    handlers.section_retrieval.assert_called_once_with(
        title=["1 前言"],
        filename="doc",
        description="前言",
        top_k=2,
    )
