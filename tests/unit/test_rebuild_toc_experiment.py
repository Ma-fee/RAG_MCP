from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from rag_mcp.indexing.rebuild_toc_experiment import (
    chunk_by_numbered_headings,
    rebuild_toc_experiment_index,
)
from rag_mcp.ingestion.document_model import Element
from rag_mcp.models import SourceDocument


def _make_doc(elements: list[Element]) -> SourceDocument:
    return SourceDocument(
        doc_id="doc-1",
        title="manual.pdf",
        relative_path="manual.pdf",
        file_type="pdf",
        text="",
        elements=elements,
    )


def test_chunk_by_numbered_headings_ignores_non_numbered_heading() -> None:
    doc = _make_doc(
        [
            Element(
                element_id="el-0",
                element_type="heading",
                text="1.5.3 Tightening Torque of Pipe Joint",
                heading_path="manual > 1.5.3",
                section_title="1.5.3 Tightening Torque of Pipe Joint",
                section_level=2,
            ),
            Element(
                element_id="el-1",
                element_type="table",
                text="",
                heading_path="manual > 1.5.3",
                section_title="1.5.3 Tightening Torque of Pipe Joint",
                section_level=2,
                metadata={"markdown": "| A | B |\n|---|---|\n| 1 | 2 |"},
            ),
            Element(
                element_id="el-2",
                element_type="heading",
                text="CAUTION",
                heading_path="manual > 1.5.3",
                section_title="CAUTION",
                section_level=2,
            ),
            Element(
                element_id="el-3",
                element_type="text",
                text="The torques in the table are for routine use only.",
                heading_path="manual > 1.5.3",
                section_title="CAUTION",
                section_level=2,
            ),
            Element(
                element_id="el-4",
                element_type="heading",
                text="1.5.4 Connection of O-rings",
                heading_path="manual > 1.5.4",
                section_title="1.5.4 Connection of O-rings",
                section_level=2,
            ),
            Element(
                element_id="el-5",
                element_type="text",
                text="O-ring installation details.",
                heading_path="manual > 1.5.4",
                section_title="1.5.4 Connection of O-rings",
                section_level=2,
            ),
        ]
    )

    chunks = chunk_by_numbered_headings(doc, min_chunk_length=1)

    assert len(chunks) == 2
    assert "1.5.3 Tightening Torque of Pipe Joint" in chunks[0].text
    assert "CAUTION" in chunks[0].text
    assert "1.5.4 Connection of O-rings" in chunks[1].text


def test_rebuild_toc_experiment_builds_chunk_resource_mapping(tmp_path: Path) -> None:
    source_dir = tmp_path / "corpus"
    data_dir = tmp_path / "data"
    source_dir.mkdir(parents=True)

    fake_doc = _make_doc(
        [
            Element(
                element_id="el-0",
                element_type="heading",
                text="1.5.3 Tightening Torque of Pipe Joint",
                heading_path="manual > 1.5.3",
                section_title="1.5.3 Tightening Torque of Pipe Joint",
                section_level=2,
            ),
            Element(
                element_id="el-1",
                element_type="text",
                text="The torques in the table are for routine use only.",
                heading_path="manual > 1.5.3",
                section_title="1.5.3 Tightening Torque of Pipe Joint",
                section_level=2,
            ),
            Element(
                element_id="el-2",
                element_type="table",
                text="",
                heading_path="manual > 1.5.3",
                section_title="1.5.3 Tightening Torque of Pipe Joint",
                section_level=2,
                metadata={"markdown": "| A | B |\n|---|---|\n| 1 | 2 |", "caption": "Table 2.4"},
            ),
            Element(
                element_id="el-3",
                element_type="image",
                text="Fig 1-31",
                heading_path="manual > 1.5.3",
                section_title="1.5.3 Tightening Torque of Pipe Joint",
                section_level=2,
                metadata={"caption": "Fig 1-31", "image_path": "assets/image-0.png"},
            ),
        ]
    )

    with patch("rag_mcp.indexing.rebuild_toc_experiment.load_supported_documents", return_value=[fake_doc]):
        result = rebuild_toc_experiment_index(source_dir=source_dir, data_dir=data_dir, min_chunk_length=1)

    assert result["chunk_count"] == 1
    assert result["resource_count"] == 3

    chunk_store = json.loads(Path(result["chunk_store"]).read_text(encoding="utf-8"))
    resource_store = json.loads(Path(result["resource_store"]).read_text(encoding="utf-8"))

    chunk = chunk_store["entries"][0]
    related_uris = chunk["related_resource_uris"]
    assert any("#table-0" in uri for uri in related_uris)
    assert any("#image-0" in uri for uri in related_uris)

    table_entry = next(e for e in resource_store["entries"] if e["type"] == "table")
    image_entry = next(e for e in resource_store["entries"] if e["type"] == "image")
    assert chunk["uri"] in table_entry["related"]
    assert chunk["uri"] in image_entry["related"]
