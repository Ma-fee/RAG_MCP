from __future__ import annotations

from pathlib import Path

from rag_mcp.ingestion.docling_parser import parse_document_file
from rag_mcp.ingestion.filesystem import load_supported_documents


def test_docling_parser_supports_md_txt_pdf(tmp_path: Path) -> None:
    md = tmp_path / "spec.md"
    md.write_text("# Doc\n\n## Scope\n\nmarkdown content", encoding="utf-8")
    txt = tmp_path / "notes.txt"
    txt.write_text("plain txt content", encoding="utf-8")
    pdf = tmp_path / "spec.pdf"
    pdf.write_text("BT (pdf semantic content) Tj ET", encoding="utf-8")

    md_doc = parse_document_file(md, tmp_path)
    txt_doc = parse_document_file(txt, tmp_path)
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
    (tmp_path / "spec.pdf").write_text("BT (pdf text) Tj ET", encoding="utf-8")
    (tmp_path / "ignore.json").write_text("{}", encoding="utf-8")

    docs = load_supported_documents(tmp_path)
    rel_paths = sorted(doc.relative_path for doc in docs)
    assert rel_paths == ["notes.txt", "spec.md", "spec.pdf"]
