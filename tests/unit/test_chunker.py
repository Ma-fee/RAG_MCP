from __future__ import annotations

from pathlib import Path

from rag_mcp.chunking.chunker import Chunker
from rag_mcp.ingestion.filesystem import load_supported_documents
from rag_mcp.models import SourceDocument


def test_load_supported_documents_only_reads_md_and_txt(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Title\n\nhello", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("plain text", encoding="utf-8")
    (tmp_path / "ignore.json").write_text("{}", encoding="utf-8")

    docs = load_supported_documents(tmp_path)

    rel_paths = sorted(doc.relative_path for doc in docs)
    assert rel_paths == ["README.md", "notes.txt"]


def test_chunker_prefers_markdown_headings_for_heading_path() -> None:
    doc = SourceDocument(
        doc_id="doc-1",
        title="README.md",
        relative_path="README.md",
        file_type="md",
        text=(
            "# RFC\n\n"
            "intro section text.\n\n"
            "## Design\n\n"
            "design details paragraph one.\n\n"
            "design details paragraph two."
        ),
    )
    chunker = Chunker(chunk_size=48, chunk_overlap=8)

    chunks = chunker.chunk_document(doc)

    assert chunks
    assert chunks[0].heading_path.startswith("RFC")
    assert any("RFC > Design" in chunk.heading_path for chunk in chunks)
    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))


def test_chunker_fallback_for_txt_sets_stable_heading_path() -> None:
    doc = SourceDocument(
        doc_id="doc-2",
        title="notes.txt",
        relative_path="notes.txt",
        file_type="txt",
        text=(
            "line1 line2 line3 line4 line5 line6 line7 line8 line9 line10 "
            "line11 line12 line13 line14 line15 line16 line17 line18"
        ),
    )
    chunker = Chunker(chunk_size=40, chunk_overlap=10)

    chunks = chunker.chunk_document(doc)

    assert len(chunks) >= 2
    assert all(chunk.heading_path == "notes.txt" for chunk in chunks)
    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))
