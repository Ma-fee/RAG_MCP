from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from rag_mcp.ingestion.docling_parser import parse_document_file
from rag_mcp.ingestion.document_model import Element


def _toc_range(level: int, title: str, heading_path: str, page_start: int, page_end: int):
    return SimpleNamespace(
        level=level,
        title=title,
        heading_path=heading_path,
        page_start=page_start,
        page_end=page_end,
    )


def _make_prov(page_no: int = 1):
    prov = MagicMock()
    prov.page_no = page_no
    return prov


def _make_text_item(text: str, label_value: str = "text", page_no: int = 1):
    item = MagicMock()
    item.text = text
    item.label = MagicMock()
    item.label.value = label_value
    item.prov = [_make_prov(page_no)]
    item.captions = []
    return item


def _make_table_item(markdown: str = "| a |\n|---|\n| 1 |", caption: str = "", page_no: int = 1):
    item = MagicMock()
    item.label = MagicMock()
    item.label.value = "table"
    item.prov = [_make_prov(page_no)]
    item.export_to_markdown.return_value = markdown
    cap = MagicMock()
    cap.text = caption
    item.captions = [cap] if caption else []
    item.data = MagicMock()
    return item


def _make_picture_item(caption: str = "", page_no: int = 1):
    item = MagicMock()
    item.label = MagicMock()
    item.label.value = "picture"
    item.prov = [_make_prov(page_no)]
    cap = MagicMock()
    cap.text = caption
    item.captions = [cap] if caption else []
    pil_img = MagicMock()
    pil_img.save = MagicMock()
    item.get_image.return_value = pil_img
    return item


def _make_converter_result(items):
    """Build a mock DocumentConverter result with given items."""
    mock_doc = MagicMock()
    mock_doc.model_dump_json.return_value = "{}"
    mock_doc.iterate_items.return_value = [(item, None) for item in items]
    mock_result = MagicMock()
    mock_result.document = mock_doc
    mock_converter = MagicMock()
    mock_converter.convert.return_value = mock_result
    return mock_converter, mock_doc


def test_parse_pdf_text_elements_have_heading_path(tmp_path):
    """Text elements should use TOC-derived heading_path in strict TOC mode."""
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.4")

    heading = _make_text_item("Chapter 1", label_value="section_header", page_no=1)
    body = _make_text_item("Some content here.", label_value="text", page_no=1)

    mock_converter, mock_doc = _make_converter_result([heading, body])

    toc_ranges = [_toc_range(2, "1.1 Safety Warning", "1 Preface > 1.1 Safety Warning", 1, 25)]
    with (
        patch("rag_mcp.ingestion.docling_parser.DocumentConverter", return_value=mock_converter),
        patch("rag_mcp.ingestion.docling_parser._extract_pdf_toc_ranges", return_value=toc_ranges),
    ):
        doc = parse_document_file(pdf, tmp_path)

    text_els = [e for e in doc.elements if e.element_type == "text"]
    assert len(text_els) >= 1
    assert text_els[0].heading_path == "1 Preface > 1.1 Safety Warning"


def test_parse_pdf_table_elements_extracted(tmp_path):
    """Table elements should be extracted with markdown content."""
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.4")

    table = _make_table_item(markdown="| col |\n|-----|\n| val |", caption="表1-1", page_no=2)

    mock_converter, mock_doc = _make_converter_result([table])

    toc_ranges = [_toc_range(2, "2.4 Notices", "2 Safety > 2.4 Notices", 1, 30)]
    with (
        patch("rag_mcp.ingestion.docling_parser.DocumentConverter", return_value=mock_converter),
        patch("rag_mcp.ingestion.docling_parser._extract_pdf_toc_ranges", return_value=toc_ranges),
    ):
        doc = parse_document_file(pdf, tmp_path)

    table_els = [e for e in doc.elements if e.element_type == "table"]
    assert len(table_els) == 1
    assert table_els[0].metadata["markdown"] == "| col |\n|-----|\n| val |"
    assert table_els[0].metadata["caption"] == "表1-1"
    assert table_els[0].metadata["page_number"] == 2


def test_parse_pdf_image_elements_saved_to_assets(tmp_path):
    """Picture elements should be saved to assets_dir and have image_path in metadata."""
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    assets_dir = tmp_path / "assets"

    picture = _make_picture_item(caption="图3-5", page_no=3)

    mock_converter, mock_doc = _make_converter_result([picture])

    toc_ranges = [_toc_range(2, "3.2 Images", "3 Structure > 3.2 Images", 1, 30)]
    with (
        patch("rag_mcp.ingestion.docling_parser.DocumentConverter", return_value=mock_converter),
        patch("rag_mcp.ingestion.docling_parser._extract_pdf_toc_ranges", return_value=toc_ranges),
    ):
        doc = parse_document_file(pdf, tmp_path, assets_dir=assets_dir)

    img_els = [e for e in doc.elements if e.element_type == "image"]
    assert len(img_els) == 1
    assert img_els[0].metadata["caption"] == "图3-5"
    assert img_els[0].metadata["page_number"] == 3
    assert "image_path" in img_els[0].metadata


def test_parse_pdf_exports_markdown_file(tmp_path):
    """When Docling document supports markdown export, parser should save a .md file."""
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    assets_dir = tmp_path / "assets"

    body = _make_text_item("Some content here.", label_value="text", page_no=1)
    mock_converter, mock_doc = _make_converter_result([body])
    mock_doc.export_to_markdown.return_value = "# Exported\n\nhello"

    toc_ranges = [_toc_range(1, "1 Preface", "1 Preface", 1, 10)]
    with (
        patch("rag_mcp.ingestion.docling_parser.DocumentConverter", return_value=mock_converter),
        patch("rag_mcp.ingestion.docling_parser._extract_pdf_toc_ranges", return_value=toc_ranges),
    ):
        doc = parse_document_file(pdf, tmp_path, assets_dir=assets_dir)

    md_file = assets_dir / "test.md"
    assert md_file.exists()
    assert "# Exported" in md_file.read_text(encoding="utf-8")
    assert doc.metadata["pdf_markdown_path"] == str(md_file)


def test_parse_pdf_cached_keeps_metadata(tmp_path):
    """Element cache load should keep document metadata fields."""
    from rag_mcp.ingestion.docling_parser import parse_document_file_cached

    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    assets_dir = tmp_path / "assets"
    cache_dir = tmp_path / "cache"

    body = _make_text_item("Some content here.", label_value="text", page_no=1)
    mock_converter, mock_doc = _make_converter_result([body])
    mock_doc.export_to_markdown.return_value = "# Exported\n\nhello"

    toc_ranges = [_toc_range(1, "1 Preface", "1 Preface", 1, 10)]
    with (
        patch("rag_mcp.ingestion.docling_parser.DocumentConverter", return_value=mock_converter),
        patch("rag_mcp.ingestion.docling_parser._extract_pdf_toc_ranges", return_value=toc_ranges),
    ):
        doc1 = parse_document_file_cached(pdf, tmp_path, assets_dir=assets_dir, cache_dir=cache_dir)

    with patch("rag_mcp.ingestion.docling_parser.DocumentConverter") as converter_patch:
        doc2 = parse_document_file_cached(pdf, tmp_path, assets_dir=assets_dir, cache_dir=cache_dir)

    converter_patch.assert_not_called()
    assert doc1.metadata.get("pdf_markdown_path")
    assert doc2.metadata.get("pdf_markdown_path") == doc1.metadata.get("pdf_markdown_path")


def test_parse_pdf_skips_page_headers_footers(tmp_path):
    """Page headers and footers should not appear as text elements."""
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.4")

    header = _make_text_item("CONFIDENTIAL", label_value="page_header")
    footer = _make_text_item("Page 1", label_value="page_footer")
    body = _make_text_item("Real content.", label_value="text")

    mock_converter, mock_doc = _make_converter_result([header, footer, body])

    toc_ranges = [_toc_range(1, "1 Preface", "1 Preface", 1, 10)]
    with (
        patch("rag_mcp.ingestion.docling_parser.DocumentConverter", return_value=mock_converter),
        patch("rag_mcp.ingestion.docling_parser._extract_pdf_toc_ranges", return_value=toc_ranges),
    ):
        doc = parse_document_file(pdf, tmp_path)

    text_els = [e for e in doc.elements if e.element_type == "text"]
    texts = [e.text for e in text_els]
    assert "CONFIDENTIAL" not in texts
    assert "Page 1" not in texts
    assert "Real content." in texts


def test_parse_pdf_without_toc_drops_elements_in_strict_mode(tmp_path):
    """Strict TOC mode should discard PDF elements when no TOC ranges exist."""
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.4")

    body = _make_text_item("Some content here.", label_value="text", page_no=1)
    mock_converter, _mock_doc = _make_converter_result([body])

    with (
        patch("rag_mcp.ingestion.docling_parser.DocumentConverter", return_value=mock_converter),
        patch("rag_mcp.ingestion.docling_parser._extract_pdf_toc_ranges", return_value=[]),
    ):
        doc = parse_document_file(pdf, tmp_path)

    assert doc.elements == []


def test_parse_md_still_works(tmp_path):
    """Markdown parsing should be unaffected by PDF changes."""
    md = tmp_path / "doc.md"
    md.write_text("# Title\n\n## Section\n\ncontent here", encoding="utf-8")
    doc = parse_document_file(md, tmp_path)
    assert doc.file_type == "md"
    text_els = [e for e in doc.elements if e.element_type == "text"]
    assert any("content here" in e.text for e in text_els)


def test_parse_txt_still_works(tmp_path):
    """Plain text parsing should be unaffected."""
    txt = tmp_path / "notes.txt"
    txt.write_text("plain text content", encoding="utf-8")
    doc = parse_document_file(txt, tmp_path)
    assert doc.file_type == "txt"
    assert doc.elements[0].text == "plain text content"
