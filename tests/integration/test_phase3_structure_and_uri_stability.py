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


def _text_doc(doc_id: str, relative_path: str, text: str) -> SourceDocument:
    title = Path(relative_path).name
    return SourceDocument(
        doc_id=doc_id,
        title=title,
        relative_path=relative_path,
        file_type="md",
        text=text,
        elements=[
            Element(
                element_id=f"{title}-t-1",
                element_type="text",
                text=text,
                heading_path=title,
                section_title=title,
                section_level=0,
            )
        ],
    )


def _uris_for_path(data_dir: Path, relative_path: str) -> list[str]:
    import json

    from rag_mcp.indexing.manifest import read_active_manifest

    manifest = read_active_manifest(data_dir / "active_index.json")
    assert manifest is not None
    entries = json.loads((Path(manifest["index_dir"]) / "keyword_store.json").read_text())[
        "entries"
    ]
    return [
        entry["uri"]
        for entry in entries
        if entry["metadata"]["relative_path"] == relative_path
    ]


def test_unrelated_doc_change_does_not_drift_other_doc_uris(
    tmp_path: Path, monkeypatch
) -> None:
    source_dir = tmp_path / "corpus"
    data_dir = tmp_path / "data"
    source_dir.mkdir(parents=True, exist_ok=True)

    state = {"round": 1}

    def _fake_loader(_directory: Path) -> list[SourceDocument]:
        stable = _text_doc(
            doc_id="slot0" if state["round"] == 1 else "slot1",
            relative_path="stable.md",
            text="stable content that should keep uri",
        )
        noisy = _text_doc(
            doc_id="noise",
            relative_path="noise.md",
            text=(
                "noise v1"
                if state["round"] == 1
                else "noise v2 with many extra tokens " * 8
            ),
        )
        return [stable, noisy] if state["round"] == 1 else [noisy, stable]

    monkeypatch.setattr("rag_mcp.indexing.rebuild.load_supported_documents", _fake_loader)

    rebuild_keyword_index(source_dir=source_dir, data_dir=data_dir, chunk_size=64, chunk_overlap=16)
    first_uris = _uris_for_path(data_dir, "stable.md")
    assert first_uris

    state["round"] = 2
    rebuild_keyword_index(source_dir=source_dir, data_dir=data_dir, chunk_size=64, chunk_overlap=16)
    second_uris = _uris_for_path(data_dir, "stable.md")

    assert second_uris == first_uris
