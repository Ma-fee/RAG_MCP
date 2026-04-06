from __future__ import annotations

from pathlib import Path
from typing import Any

from rag_mcp.chunking.toc_chunker import TocAwareChunker
import rag_mcp.indexing.services as services_module
from rag_mcp.indexing.services import RebuildIndexService
from rag_mcp.ingestion.filesystem import load_supported_documents


def rebuild_keyword_index(
    source_dir: Path,
    data_dir: Path,
    chunk_size: int = 800,
    chunk_overlap: int = 120,
    min_chunk_length: int = 30,
    embedding_provider: Any | None = None,
    vlm_client: Any | None = None,
) -> dict[str, Any]:
    # chunk_size/chunk_overlap are kept for backward compatibility in the public API.
    del chunk_size, chunk_overlap
    # Keep test patch paths stable by forwarding rebuild-module symbols.
    services_module.load_supported_documents = load_supported_documents
    services_module.TocAwareChunker = TocAwareChunker
    service = RebuildIndexService()
    service._build_and_persist_keyword_store = (  # type: ignore[method-assign]
        lambda **kwargs: _build_and_persist_keyword_store(service=service, **kwargs)
    )
    return service.rebuild_keyword_index(
        source_dir=source_dir,
        data_dir=data_dir,
        min_chunk_length=min_chunk_length,
        embedding_provider=embedding_provider,
        vlm_client=vlm_client,
    )


def _build_and_persist_keyword_store(
    *,
    service: RebuildIndexService,
    source_dir: Path,
    data_dir: Path,
    corpus_id: str,
    index_dir: Path,
    min_chunk_length: int,
    embedding_provider: Any | None,
    vlm_client: Any | None = None,
) -> dict[str, int]:
    return RebuildIndexService._build_and_persist_keyword_store(
        service,
        source_dir=source_dir,
        data_dir=data_dir,
        corpus_id=corpus_id,
        index_dir=index_dir,
        min_chunk_length=min_chunk_length,
        embedding_provider=embedding_provider,
        vlm_client=vlm_client,
    )
