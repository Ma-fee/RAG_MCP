from __future__ import annotations

import xml.etree.ElementTree as ET

from rag_mcp.errors import ErrorCode
from rag_mcp.xml_response import build_error_response, build_ok_response


def test_build_ok_response_wraps_payload_with_response_envelope() -> None:
    xml_text = build_ok_response(
        "index-status",
        {
            "has_active_index": "false",
            "corpus_id": "none",
        },
    )

    root = ET.fromstring(xml_text)
    assert root.tag == "response"
    assert root.findtext("status") == "ok"
    assert root.findtext("data/index-status/has_active_index") == "false"
    assert root.findtext("data/index-status/corpus_id") == "none"


def test_build_error_response_includes_error_fields() -> None:
    xml_text = build_error_response(
        code=ErrorCode.NO_ACTIVE_INDEX,
        message="当前没有活动索引",
        hint="请先调用 rag_rebuild_index",
    )

    root = ET.fromstring(xml_text)
    assert root.tag == "response"
    assert root.findtext("status") == "error"
    assert root.findtext("error/code") == "NO_ACTIVE_INDEX"
    assert root.findtext("error/message") == "当前没有活动索引"
    assert root.findtext("error/hint") == "请先调用 rag_rebuild_index"


def test_error_code_catalog_contains_phase1_modes() -> None:
    assert ErrorCode.UNSUPPORTED_SEARCH_MODE.value == "UNSUPPORTED_SEARCH_MODE"
    assert (
        ErrorCode.SEARCH_MODE_NOT_IMPLEMENTED.value
        == "SEARCH_MODE_NOT_IMPLEMENTED"
    )
