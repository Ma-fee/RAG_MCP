from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from rag_mcp.ingestion.docling_parser import parse_document_file
from rag_mcp.ingestion.filesystem import load_supported_documents


def _make_mock_converter():
    mock_doc = MagicMock()
    mock_doc.iterate_items.return_value = []
    mock_result = MagicMock()
    mock_result.document = mock_doc
    mock_converter = MagicMock()
    mock_converter.convert.return_value = mock_result
    return mock_converter


def test_docling_parser_supports_md_txt_pdf(tmp_path: Path) -> None:
    md = tmp_path / "spec.md"
    md.write_text("# Doc\n\n## Scope\n\nmarkdown content", encoding="utf-8")
    txt = tmp_path / "notes.txt"
    txt.write_text("plain txt content", encoding="utf-8")
    pdf = tmp_path / "spec.pdf"
    pdf.write_bytes(b"%PDF-1.4")

    md_doc = parse_document_file(md, tmp_path)
    txt_doc = parse_document_file(txt, tmp_path)

    with patch("rag_mcp.ingestion.docling_parser.DocumentConverter", return_value=_make_mock_converter()):
        pdf_doc = parse_document_file(pdf, tmp_path)

    assert md_doc.file_type == "md"
    assert txt_doc.file_type == "txt"
    assert pdf_doc.file_type == "pdf"
    assert md_doc.elements
    assert txt_doc.elements
    assert pdf_doc.elements


def test_load_supported_documents_includes_pdf(tmp_path: Path) -> None:
    (tmp_path / "spec.md").write_text("# A\n\nB", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("hello", encoding="utf-8")
    (tmp_path / "spec.pdf").write_bytes(b"%PDF-1.4")
    (tmp_path / "ignore.json").write_text("{}", encoding="utf-8")

    with patch("rag_mcp.ingestion.filesystem.parse_document_file") as mock_parse:
        from rag_mcp.ingestion.document_model import Document, Element
        def fake_parse(path, root_dir, **kwargs):
            rel = path.relative_to(root_dir).as_posix()
            el = Element(element_id="el-0", element_type="text", text="x",
                        heading_path="t", section_title="t", section_level=0)
            return Document(doc_id="id", title=path.name, relative_path=rel,
                           file_type=path.suffix.lstrip("."), elements=[el])
        mock_parse.side_effect = fake_parse
        docs = load_supported_documents(tmp_path)

    rel_paths = sorted(doc.relative_path for doc in docs)
    assert rel_paths == ["notes.txt", "spec.md", "spec.pdf"]
