from __future__ import annotations

from pathlib import Path

from rag_mcp.indexing.rebuild import rebuild_keyword_index
from rag_mcp.ingestion.document_model import Element
from rag_mcp.models import SourceDocument
from rag_mcp.resources.service import ResourceService
from rag_mcp.retrieval.service import RetrievalService


def _structured_doc() -> SourceDocument:
    elements = [
        Element(
            element_id="h-1",
            element_type="heading",
            text="Intro",
            heading_path="Spec > Intro",
            section_title="Intro",
            section_level=1,
        ),
        Element(
            element_id="t-1",
            element_type="text",
            text="intro baseline section",
            heading_path="Spec > Intro",
            section_title="Intro",
            section_level=1,
        ),
        Element(
            element_id="tbl-1",
            element_type="table",
            text="| A | B |",
            heading_path="Spec > Intro",
            section_title="Intro",
            section_level=1,
        ),
        Element(
            element_id="img-1",
            element_type="image",
            text="diagram",
            heading_path="Spec > Intro",
            section_title="Intro",
            section_level=1,
        ),
        Element(
            element_id="h-2",
            element_type="heading",
            text="Design",
            heading_path="Spec > Design",
            section_title="Design",
            section_level=1,
        ),
        Element(
            element_id="t-2",
            element_type="text",
            text="design details only",
            heading_path="Spec > Design",
            section_title="Design",
            section_level=1,
        ),
    ]
    return SourceDocument(
        doc_id="docstructured1",
        title="spec.md",
        relative_path="spec.md",
        file_type="md",
        text="intro baseline section design details only",
        elements=elements,
    )


def test_table_and_image_ids_only_exposed_in_resource_metadata(
    tmp_path: Path, monkeypatch
) -> None:
    source_dir = tmp_path / "corpus"
    data_dir = tmp_path / "data"
    source_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        "rag_mcp.indexing.rebuild.load_supported_documents",
        lambda _directory: [_structured_doc()],
    )

    rebuild_keyword_index(source_dir=source_dir, data_dir=data_dir, chunk_size=256)

    retrieval = RetrievalService(data_dir=data_dir)
    resource_service = ResourceService(data_dir=data_dir)

    search_payload = retrieval.search(query="intro baseline", mode="keyword", top_k=3)
    assert search_payload["results"]
    top = search_payload["results"][0]
    assert "table_element_ids" not in top["metadata"]
    assert "image_element_ids" not in top["metadata"]

    resource_payload = resource_service.read(top["uri"])
    assert resource_payload["metadata"]["table_element_ids"] == ["tbl-1"]
    assert resource_payload["metadata"]["image_element_ids"] == ["img-1"]
