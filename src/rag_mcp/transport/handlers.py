from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rag_mcp.errors import ErrorCode, ServiceError, ServiceException
from rag_mcp.ingestion.filesystem import load_supported_documents
from rag_mcp.indexing.manifest import read_active_manifest
from rag_mcp.indexing.rebuild import rebuild_keyword_index
from rag_mcp.resources.service import ResourceService
from rag_mcp.retrieval.service import RetrievalService


class ToolHandlers:
    def __init__(
        self,
        data_dir: Path,
        embedding_provider: Any | None = None,
        vlm_client: Any | None = None,
        reranker: Any | None = None,
        rerank_top_k_candidates: int = 20,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.embedding_provider = embedding_provider
        self.vlm_client = vlm_client
        self.retrieval = RetrievalService(
            self.data_dir,
            embedding_provider=self.embedding_provider,
            reranker=reranker,
            rerank_top_k_candidates=rerank_top_k_candidates,
        )
        self.resources = ResourceService(self.data_dir)

    def rebuild_index(self, directory_path: str) -> dict:
        source_dir = Path(directory_path)
        if not source_dir.exists() or not source_dir.is_dir():
            return {"error": "invalid_directory", "message": "目录不存在或路径无效"}
        if not load_supported_documents(source_dir):
            return {"error": "no_documents", "message": "目录中没有可索引文档"}
        try:
            result = rebuild_keyword_index(
                source_dir=source_dir,
                data_dir=self.data_dir,
                embedding_provider=self.embedding_provider,
                vlm_client=self.vlm_client,
            )
            return {
                "corpus_id": result["corpus_id"],
                "source_directory": directory_path,
                "document_count": result["document_count"],
                "chunk_count": result["chunk_count"],
                "indexed_at": result["indexed_at"],
            }
        except Exception as exc:
            return {"error": "rebuild_failed", "message": str(exc)}

    def index_status(self) -> dict:
        manifest = read_active_manifest(self.data_dir / "active_index.json")
        if manifest is None:
            return {"has_active_index": False}

        filenames: list[str] = []
        try:
            grouped = self._group_entries_by_document()
            filenames = sorted(grouped.keys())
        except ServiceException:
            filenames = []

        return {
            "has_active_index": True,
            "corpus_id": manifest["corpus_id"],
            "document_count": manifest["document_count"],
            "chunk_count": manifest["chunk_count"],
            "indexed_at": manifest["indexed_at"],
            "filenames": filenames,
        }

    def search(self, query: str, top_k: int = 5) -> dict:
        try:
            return self.retrieval.search(query=query, top_k=top_k)
        except ServiceException as exc:
            return {"error": exc.error.code.value, "message": exc.error.message}

    def read_resource(self, uri: str) -> dict:
        try:
            return self.resources.read(uri)
        except ServiceException as exc:
            return {"error": exc.error.code.value, "message": exc.error.message}

    def read_resources(self, uris: list[str]) -> dict:
        if not uris:
            return {
                "count": 0,
                "success_count": 0,
                "error_count": 0,
                "results": [],
            }

        results: list[dict[str, Any]] = []
        success_count = 0
        error_count = 0

        for uri in uris:
            try:
                payload = self.resources.read(uri=uri)
                results.append({"uri": uri, "ok": True, "resource": payload})
                success_count += 1
            except ServiceException as exc:
                results.append(
                    {
                        "uri": uri,
                        "ok": False,
                        "error": exc.error.code.value,
                        "message": exc.error.message,
                    }
                )
                error_count += 1

        return {
            "count": len(uris),
            "success_count": success_count,
            "error_count": error_count,
            "results": results,
        }

    def list_filenames(self) -> dict:
        try:
            grouped = self._group_entries_by_document()
        except ServiceException as exc:
            return {"error": exc.error.code.value, "message": exc.error.message}

        filenames = []
        for doc_key, payload in sorted(grouped.items(), key=lambda item: item[0]):
            filenames.append(
                {
                    "filename": doc_key,
                    "file_type": payload["file_type"],
                    "chunk_count": len(payload["entries"]),
                }
            )

        return {"count": len(filenames), "filenames": filenames}

    def list_sections(self, filename: str) -> dict:
        if not filename or not filename.strip():
            return {"error": "missing_filename", "message": "filename 不能为空"}

        normalized_filename = filename.strip()
        try:
            sections_mapping = self._load_sections_mapping()
        except ServiceException as exc:
            return {"error": exc.error.code.value, "message": exc.error.message}

        sections = sections_mapping.get(normalized_filename)
        if sections is None:
            return {
                "error": "invalid_filename",
                "message": f"未找到文档: {normalized_filename}",
            }

        return {normalized_filename: sections}

    def section_retrieval(
        self,
        section_title: list[str],
        filename: str,
    ) -> dict:
        if not filename or not filename.strip():
            return {"error": "missing_filename", "message": "filename 不能为空"}

        normalized_titles = [
            item.strip() for item in section_title if item and item.strip()
        ]
        if not normalized_titles:
            return {
                "error": "missing_section_title",
                "message": "section_title 不能为空",
            }

        try:
            grouped = self._group_entries_by_document()
        except ServiceException as exc:
            return {"error": exc.error.code.value, "message": exc.error.message}

        normalized_filename = filename.strip()
        doc_payload = grouped.get(normalized_filename)
        if doc_payload is None:
            return {
                "error": "invalid_filename",
                "message": f"未找到文档: {normalized_filename}",
            }

        valid_section_titles = set()
        try:
            valid_section_titles = set(self._load_sections_mapping().get(normalized_filename, []))
        except ServiceException:
            valid_section_titles = {
                section["title"]
                for section in self._extract_sections_from_entries(doc_payload["entries"])
            }

        invalid_titles = [item for item in normalized_titles if item not in valid_section_titles]
        if invalid_titles:
            return {
                "error": "invalid_title",
                "message": "title 必须与 list_sections 返回的章节标题完全一致",
                "invalid_titles": invalid_titles,
            }

        matched_results: list[dict[str, Any]] = []
        title_set = set(normalized_titles)

        # Build URI map from keyword store entries to enrich vector hits with related resources.
        uri_to_entry = {
            str(entry.get("uri", "")): entry
            for entry in doc_payload["entries"]
            if entry.get("uri")
        }

        for entry in doc_payload["entries"]:
            metadata = entry.get("metadata", {})
            entry_section_title = str(metadata.get("section_title", "")).strip()
            if entry_section_title not in title_set:
                continue

            entry_uri = str(entry.get("uri", ""))
            related_uris = uri_to_entry.get(entry_uri, {}).get(
                "related_resource_uris", []
            )
            matched_results.append(
                {
                    "filename": normalized_filename,
                    "uri": entry.get("uri"),
                    "title": entry_section_title,
                    "text": entry.get("text", ""),
                    "metadata": metadata,
                    "related_resource_uris": related_uris,
                    "related_resources": self._resolve_related_resources(related_uris),
                }
            )

        matched_results.sort(
            key=lambda item: int(item.get("metadata", {}).get("chunk_index", 0))
        )

        return {
            "filename": normalized_filename,
            "requested_section_titles": normalized_titles,
            "result_count": len(matched_results),
            "results": matched_results,
        }

    def _resolve_related_resources(self, related_uris: list[str]) -> list[dict[str, Any]]:
        resolved: list[dict[str, Any]] = []
        for uri in related_uris:
            try:
                resolved.append(self.resources.read(uri=uri))
            except ServiceException:
                continue
        return resolved

    def _group_entries_by_document(self) -> dict[str, dict[str, Any]]:
        manifest = read_active_manifest(self.data_dir / "active_index.json")
        if manifest is None:
            raise ServiceException(
                ServiceError(
                    code=ErrorCode.NO_ACTIVE_INDEX,
                    message="当前没有活动索引",
                    hint="请先调用 rag_rebuild_index",
                )
            )

        index_dir = Path(manifest["index_dir"])
        keyword_store_path = index_dir / "keyword_store.json"
        if not keyword_store_path.exists():
            raise ServiceException(
                ServiceError(
                    code=ErrorCode.RESOURCE_NOT_FOUND,
                    message="未找到 keyword_store.json",
                    hint="请重新执行 rag_rebuild_index",
                )
            )

        payload = json.loads(keyword_store_path.read_text(encoding="utf-8"))
        entries = payload.get("entries", [])

        grouped: dict[str, dict[str, Any]] = {}
        for entry in entries:
            metadata = entry.get("metadata", {})
            relative_path = str(metadata.get("relative_path", ""))
            filename = Path(relative_path).stem if relative_path else str(entry.get("title", ""))
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

    def _extract_sections_from_entries(
        self,
        entries: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        sections: list[dict[str, Any]] = []

        ordered_entries = sorted(
            entries,
            key=lambda item: int(item.get("metadata", {}).get("chunk_index", 0)),
        )
        for entry in ordered_entries:
            metadata = entry.get("metadata", {})
            section_title = str(metadata.get("section_title", "")).strip()
            heading_path = str(metadata.get("heading_path", "")).strip()
            title = section_title or heading_path or str(entry.get("title", "")).strip()
            if not title:
                continue

            sections.append(
                {
                    "title": title,
                    "heading_path": heading_path,
                    "section_title": section_title or title,
                    "section_level": metadata.get("section_level", 0),
                }
            )

        return sections

    def _load_sections_mapping(self) -> dict[str, list[str]]:
        manifest = read_active_manifest(self.data_dir / "active_index.json")
        if manifest is None:
            raise ServiceException(
                ServiceError(
                    code=ErrorCode.NO_ACTIVE_INDEX,
                    message="当前没有活动索引",
                    hint="请先调用 rag_rebuild_index",
                )
            )

        index_dir = Path(manifest["index_dir"])
        mapping_path = index_dir / "sections_mapping.json"
        if not mapping_path.exists():
            raise ServiceException(
                ServiceError(
                    code=ErrorCode.RESOURCE_NOT_FOUND,
                    message="未找到 sections_mapping.json",
                    hint="请先运行 sections mapping 构建脚本",
                )
            )

        payload = json.loads(mapping_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ServiceException(
                ServiceError(
                    code=ErrorCode.RESOURCE_NOT_FOUND,
                    message="sections_mapping.json 格式无效",
                    hint="请重新运行 sections mapping 构建脚本",
                )
            )
        return {
            str(k): [str(item) for item in v]
            for k, v in payload.items()
            if isinstance(v, list)
        }
