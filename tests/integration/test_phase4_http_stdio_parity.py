from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET

from rag_mcp.transport.handlers import ToolHandlers
from rag_mcp.transport.stdio_server import StdioServer


def _write_corpus(corpus_dir: Path) -> None:
    corpus_dir.mkdir(parents=True, exist_ok=True)
    (corpus_dir / "README.md").write_text(
        "# RFC\n\n## Scope\n\nkeyword retrieval parity check",
        encoding="utf-8",
    )
    (corpus_dir / "notes.txt").write_text(
        "transport parity baseline",
        encoding="utf-8",
    )


def test_shared_handlers_keep_http_and_stdio_xml_identical(tmp_path: Path) -> None:
    corpus_dir = tmp_path / "corpus"
    data_dir = tmp_path / "data"
    _write_corpus(corpus_dir)

    stdio = StdioServer(data_dir=data_dir)
    handlers = ToolHandlers(data_dir=data_dir)

    # Prepare data first; rebuild output includes time-based fields and is not parity-safe.
    stdio.rag_rebuild_index(str(corpus_dir))

    stdio_status = stdio.rag_index_status()
    http_status = handlers.handle_tool("rag_index_status", {})
    assert stdio_status == http_status

    stdio_search = stdio.rag_search("keyword retrieval", mode="keyword", top_k=3)
    http_search = handlers.handle_tool(
        "rag_search",
        {"query": "keyword retrieval", "mode": "keyword", "top_k": 3},
    )
    assert stdio_search == http_search

    root = ET.fromstring(stdio_search)
    uri = root.findtext("data/search-results/results/item/uri")
    assert uri

    stdio_read = stdio.rag_read_resource(uri)
    http_read = handlers.handle_tool("rag_read_resource", {"uri": uri})
    assert stdio_read == http_read
