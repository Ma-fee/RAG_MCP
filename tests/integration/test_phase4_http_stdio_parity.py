from __future__ import annotations

import json
from pathlib import Path
from urllib import request
import xml.etree.ElementTree as ET

from rag_mcp.errors import ErrorCode
from rag_mcp.transport.http_server import start_http_server_if_enabled
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


def test_http_transport_only_starts_when_enabled(tmp_path: Path) -> None:
    corpus_dir = tmp_path / "corpus"
    data_dir = tmp_path / "data"
    _write_corpus(corpus_dir)

    disabled_server = start_http_server_if_enabled(
        enable_http=False, data_dir=data_dir, host="127.0.0.1", port=0
    )
    assert disabled_server is None

    enabled_server = start_http_server_if_enabled(
        enable_http=True, data_dir=data_dir, host="127.0.0.1", port=0
    )
    assert enabled_server is not None
    try:
        xml_text = _http_call(
            enabled_server.endpoint_url(),
            "rag_rebuild_index",
            {"directory_path": str(corpus_dir)},
        )
        root = ET.fromstring(xml_text)
        assert root.findtext("status") == "ok"
    finally:
        enabled_server.close()


def test_error_semantics_are_consistent_and_path_safe_between_stdio_and_http(
    tmp_path: Path,
) -> None:
    corpus_dir = tmp_path / "corpus"
    data_dir = tmp_path / "data"
    _write_corpus(corpus_dir)

    stdio = StdioServer(data_dir=data_dir)
    http_server = start_http_server_if_enabled(
        enable_http=True, data_dir=data_dir, host="127.0.0.1", port=0
    )
    assert http_server is not None
    try:
        bad_path = tmp_path / "not_a_directory.txt"
        bad_path.write_text("x", encoding="utf-8")

        stdio_illegal = stdio.rag_rebuild_index(str(bad_path))
        http_illegal = _http_call(
            http_server.endpoint_url(),
            "rag_rebuild_index",
            {"directory_path": str(bad_path)},
        )
        assert stdio_illegal == http_illegal
        illegal_root = ET.fromstring(stdio_illegal)
        assert illegal_root.findtext("status") == "error"
        assert illegal_root.findtext("error/code") == ErrorCode.NO_ACTIVE_INDEX.value
        assert str(bad_path) not in (illegal_root.findtext("error/message") or "")

        empty_dir = tmp_path / "empty"
        empty_dir.mkdir(parents=True, exist_ok=True)
        stdio_empty = stdio.rag_rebuild_index(str(empty_dir))
        http_empty = _http_call(
            http_server.endpoint_url(),
            "rag_rebuild_index",
            {"directory_path": str(empty_dir)},
        )
        assert stdio_empty == http_empty
        empty_root = ET.fromstring(stdio_empty)
        assert empty_root.findtext("status") == "error"
        assert empty_root.findtext("error/code") == ErrorCode.NO_ACTIVE_INDEX.value

        ok_xml = stdio.rag_rebuild_index(str(corpus_dir))
        assert ET.fromstring(ok_xml).findtext("status") == "ok"

        missing_uri = "rag://corpus/aaaaaaaaaaaaaaaa/bbbbbbbbbbbbbbbb#chunk-0"
        stdio_missing = stdio.rag_read_resource(missing_uri)
        http_missing = _http_call(
            http_server.endpoint_url(),
            "rag_read_resource",
            {"uri": missing_uri},
        )
        assert stdio_missing == http_missing
        missing_root = ET.fromstring(stdio_missing)
        assert missing_root.findtext("status") == "error"
        assert missing_root.findtext("error/code") == ErrorCode.RESOURCE_NOT_FOUND.value
    finally:
        http_server.close()


def _http_call(endpoint: str, tool: str, args: dict[str, object]) -> str:
    payload = {"tool": tool, "args": args}
    req = request.Request(
        url=endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=5) as resp:
        return resp.read().decode("utf-8")
