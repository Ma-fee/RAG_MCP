from __future__ import annotations

from rag_mcp.indexing.cross_reference import build_cross_references


def test_regex_match_links_text_to_image():
    entries = [
        {
            "uri": "rag://c/d#text-0",
            "type": "text",
            "text": "如图3-5所示，调节阀位于泵体右侧",
            "related": [],
        },
        {
            "uri": "rag://c/d#image-0",
            "type": "image",
            "caption": "图3-5",
            "heading_path": "Chapter 1",
            "related": [],
        },
    ]
    result = build_cross_references(entries)
    text = next(e for e in result if e["uri"].endswith("#text-0"))
    image = next(e for e in result if e["uri"].endswith("#image-0"))
    assert "rag://c/d#image-0" in text["related"]
    assert "rag://c/d#text-0" in image["related"]


def test_regex_match_links_text_to_table():
    entries = [
        {
            "uri": "rag://c/d#text-0",
            "type": "text",
            "text": "具体参数见表3-2。",
            "related": [],
        },
        {
            "uri": "rag://c/d#table-0",
            "type": "table",
            "caption": "表3-2",
            "heading_path": "Chapter 1",
            "related": [],
        },
    ]
    result = build_cross_references(entries)
    text = next(e for e in result if e["uri"].endswith("#text-0"))
    table = next(e for e in result if e["uri"].endswith("#table-0"))
    assert "rag://c/d#table-0" in text["related"]
    assert "rag://c/d#text-0" in table["related"]


def test_heading_path_fallback_links_same_section():
    entries = [
        {
            "uri": "rag://c/d#text-0",
            "type": "text",
            "text": "无显式引用",
            "heading_path": "Chapter 1",
            "related": [],
        },
        {
            "uri": "rag://c/d#image-0",
            "type": "image",
            "caption": "",
            "heading_path": "Chapter 1",
            "related": [],
        },
    ]
    result = build_cross_references(entries)
    image = next(e for e in result if e["uri"].endswith("#image-0"))
    assert "rag://c/d#text-0" in image.get("related_weak", [])


def test_no_spurious_cross_section_links():
    entries = [
        {
            "uri": "rag://c/d#text-0",
            "type": "text",
            "text": "no reference here",
            "heading_path": "Chapter 1",
            "related": [],
        },
        {
            "uri": "rag://c/d#image-0",
            "type": "image",
            "caption": "",
            "heading_path": "Chapter 2",
            "related": [],
        },
    ]
    result = build_cross_references(entries)
    image = next(e for e in result if e["uri"].endswith("#image-0"))
    text = next(e for e in result if e["uri"].endswith("#text-0"))
    assert "rag://c/d#text-0" not in image.get("related_weak", [])
    assert "rag://c/d#image-0" not in text["related"]


def test_text_reference_replaced_with_markdown_link():
    entries = [
        {
            "uri": "rag://c/d#text-0",
            "type": "text",
            "text": "如图3-5所示",
            "related": [],
        },
        {
            "uri": "rag://c/d#image-0",
            "type": "image",
            "caption": "图3-5",
            "heading_path": "Chapter 1",
            "related": [],
        },
    ]
    result = build_cross_references(entries)
    text = next(e for e in result if e["uri"].endswith("#text-0"))
    assert "[图3-5](rag://c/d#image-0)" in text["text"]


def test_no_self_links():
    entries = [
        {
            "uri": "rag://c/d#text-0",
            "type": "text",
            "text": "plain text",
            "related": [],
        },
    ]
    result = build_cross_references(entries)
    text = next(e for e in result if e["uri"].endswith("#text-0"))
    assert "rag://c/d#text-0" not in text["related"]
