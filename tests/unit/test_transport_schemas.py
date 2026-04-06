from __future__ import annotations

import pytest

from rag_mcp.errors import ErrorCode, ServiceException
from rag_mcp.transport.schemas import (
    ReadResourceInput,
    SearchInput,
    SectionRetrievalInput,
    parse_input,
)


def test_parse_search_input_normalizes_query_and_default_top_k() -> None:
    payload = parse_input(SearchInput, {"query": "  hello  ", "top_k": None})
    assert payload.query == "hello"
    assert payload.top_k == 5


def test_parse_search_input_rejects_invalid_top_k() -> None:
    with pytest.raises(ServiceException) as exc:
        parse_input(SearchInput, {"query": "hello", "top_k": 0})
    assert exc.value.error.code == ErrorCode.INVALID_ARGUMENT
    assert exc.value.error.message == "top_k 必须大于等于 1"


def test_parse_read_resource_input_rejects_blank_uri() -> None:
    with pytest.raises(ServiceException) as exc:
        parse_input(ReadResourceInput, {"uri": "   "})
    assert exc.value.error.code == ErrorCode.INVALID_ARGUMENT
    assert exc.value.error.message == "uri 不能为空"


def test_parse_section_retrieval_input_normalizes_titles() -> None:
    payload = parse_input(
        SectionRetrievalInput,
        {
            "title": [" 1 前言 ", "", "2 结构"],
            "filename": " spec ",
            "description": "d",
            "top_k": None,
        },
    )
    assert payload.title == ["1 前言", "2 结构"]
    assert payload.filename == "spec"
    assert payload.top_k == 10
