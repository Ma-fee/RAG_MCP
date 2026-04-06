from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rag_mcp.catalog.models import SectionResult
from rag_mcp.errors import ErrorCode, ServiceError, ServiceException
from rag_mcp.indexing.repositories import (
    ActiveIndexRepository,
    KeywordStoreRepository,
    RepositoryError,
)
from rag_mcp.resources.service import ResourceService


@dataclass
class CatalogQueryService:
    data_dir: Path
    resources: ResourceService

    def __post_init__(self) -> None:
        self.data_dir = Path(self.data_dir)
        self.active_indexes = ActiveIndexRepository(self.data_dir)

    def list_filenames(self) -> dict[str, Any]:
        grouped = self._group_entries_by_document()
        filenames = [
            {
                "filename": doc_key,
                "file_type": payload["file_type"],
                "chunk_count": len(payload["entries"]),
            }
            for doc_key, payload in sorted(grouped.items(), key=lambda item: item[0])
        ]
        return {"count": len(filenames), "filenames": filenames}

    def list_sections(self, filename: str) -> dict[str, Any]:
        grouped = self._group_entries_by_document()
        normalized_filename = filename.strip()
        doc_payload = grouped.get(normalized_filename)
        if doc_payload is None:
            raise ServiceException(
                ServiceError(
                    code=ErrorCode.RESOURCE_NOT_FOUND,
                    message=f"未找到文档: {normalized_filename}",
                    hint="请先调用 rag_list_filenames 确认 filename",
                )
            )

        sections = self._extract_sections_from_entries(doc_payload["entries"])
        return {
            "filename": normalized_filename,
            "relative_path": doc_payload["relative_path"],
            "file_type": doc_payload["file_type"],
            "section_count": len(sections),
            "sections": sections,
        }

    def section_retrieval(
        self,
        title: list[str],
        filename: str,
        description: str = "",
        top_k: int = 10,
    ) -> dict[str, Any]:
        grouped = self._group_entries_by_document()
        normalized_filename = filename.strip()
        normalized_titles = [item.strip() for item in title if item and item.strip()]
        doc_payload = grouped.get(normalized_filename)
        if doc_payload is None:
            raise ServiceException(
                ServiceError(
                    code=ErrorCode.RESOURCE_NOT_FOUND,
                    message=f"未找到文档: {normalized_filename}",
                    hint="请先调用 rag_list_filenames 确认 filename",
                )
            )

        sections = self._extract_sections_from_entries(doc_payload["entries"])
        valid_section_titles = {section["title"] for section in sections}
        invalid_titles = [
            item for item in normalized_titles if item not in valid_section_titles
        ]
        if invalid_titles:
            raise ServiceException(
                ServiceError(
                    code=ErrorCode.RESOURCE_NOT_FOUND,
                    message="title 必须与 list_sections 返回的章节标题完全一致",
                    hint="请先调用 rag_list_sections 获取可用标题",
                    details={"invalid_titles": ",".join(invalid_titles)},
                )
            )

        query = description.strip() if description.strip() else " ".join(normalized_titles)
        title_set = set(normalized_titles)
        matched_results = []
        for entry in doc_payload["entries"]:
            entry_title = str(entry.get("title", "")).strip()
            if entry_title not in title_set:
                continue
            related_resource_uris = entry.get("related_resource_uris", [])
            matched_results.append(
                SectionResult(
                    uri=str(entry.get("uri", "")),
                    title=entry_title,
                    text=str(entry.get("text", "")),
                    metadata=entry.get("metadata", {}),
                    related_resource_uris=related_resource_uris,
                    related_resources=self._resolve_related_resources(
                        related_resource_uris
                    ),
                ).to_dict()
            )

        matched_results.sort(
            key=lambda item: int(item.get("metadata", {}).get("chunk_index", 0))
        )
        limited = matched_results[: max(1, int(top_k))]
        return {
            "query": query,
            "filename": normalized_filename,
            "requested_titles": normalized_titles,
            "result_count": len(limited),
            "results": limited,
        }

    def _group_entries_by_document(self) -> dict[str, dict[str, Any]]:
        entries = self._keyword_entries()
        grouped: dict[str, dict[str, Any]] = {}
        for entry in entries:
            metadata = entry.get("metadata", {})
            relative_path = str(metadata.get("relative_path", ""))
            filename = (
                Path(relative_path).stem if relative_path else str(entry.get("title", ""))
            )
            if not filename:
                continue
            if filename not in grouped:
                grouped[filename] = {
                    "relative_path": relative_path,
                    "file_type": str(metadata.get("file_type", "unknown")),
                    "entries": [],
                }
            grouped[filename]["entries"].append(entry)
        return grouped

    def _keyword_entries(self) -> list[dict[str, Any]]:
        try:
            manifest = self.active_indexes.load()
            index_dir = Path(manifest["index_dir"])
            return KeywordStoreRepository(index_dir=index_dir).entries()
        except RepositoryError:
            raise ServiceException(
                ServiceError(
                    code=ErrorCode.NO_ACTIVE_INDEX,
                    message="当前没有活动索引",
                    hint="请先调用 rag_rebuild_index",
                )
            )

    def _extract_sections_from_entries(
        self,
        entries: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        seen = set()
        sections: list[dict[str, Any]] = []
        ordered_entries = sorted(
            entries,
            key=lambda item: int(item.get("metadata", {}).get("chunk_index", 0)),
        )
        for entry in ordered_entries:
            metadata = entry.get("metadata", {})
            section_title = str(entry.get("title", "")).strip()
            if not section_title or section_title in seen:
                continue
            seen.add(section_title)
            sections.append(
                {
                    "title": section_title,
                    "heading_path": metadata.get("heading_path", ""),
                    "section_title": metadata.get("section_title", section_title),
                    "section_level": metadata.get("section_level", 0),
                }
            )
        return sections

    def _resolve_related_resources(self, related_uris: list[str]) -> list[dict[str, Any]]:
        resources: list[dict[str, Any]] = []
        for uri in related_uris:
            try:
                resources.append(self.resources.read(uri))
            except ServiceException:
                continue
        return resources
