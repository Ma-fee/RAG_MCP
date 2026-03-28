from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from rag_mcp.config import AppConfig
from rag_mcp.errors import ErrorCode, ServiceException
from rag_mcp.indexing.manifest import read_active_manifest
from rag_mcp.indexing.rebuild import rebuild_keyword_index
from rag_mcp.resources.service import ResourceService
from rag_mcp.retrieval.service import RetrievalService
from rag_mcp.xml_response import build_error_response, build_ok_response


class StdioServer:
    def __init__(
        self, data_dir: Path | None = None, embedding_provider: Any | None = None
    ) -> None:
        cfg = AppConfig.from_env()
        self.data_dir = Path(data_dir) if data_dir is not None else cfg.data_dir
        self.embedding_provider = embedding_provider
        self.retrieval = RetrievalService(
            self.data_dir, embedding_provider=self.embedding_provider
        )
        self.resources = ResourceService(self.data_dir)

    def rag_rebuild_index(self, directory_path: str) -> str:
        try:
            result = rebuild_keyword_index(
                source_dir=Path(directory_path),
                data_dir=self.data_dir,
                embedding_provider=self.embedding_provider,
            )
            payload = {
                "corpus_id": result["corpus_id"],
                "source_directory": directory_path,
                "document_count": result["document_count"],
                "chunk_count": result["chunk_count"],
                "indexed_at": str(result["indexed_at"]),
            }
            return build_ok_response("index-rebuild-result", payload)
        except FileNotFoundError:
            return build_error_response(
                code=ErrorCode.NO_ACTIVE_INDEX,
                message="目录不存在",
                hint="请检查 directory_path",
            )
        except Exception as exc:
            return build_error_response(
                code=ErrorCode.NO_ACTIVE_INDEX,
                message=f"索引重建失败: {exc}",
                hint="请检查目录和文件内容",
            )

    def rag_index_status(self) -> str:
        manifest = read_active_manifest(self.data_dir / "active_index.json")
        if manifest is None:
            payload = {"has_active_index": "false"}
            return build_ok_response("index-status", payload)

        payload = {
            "has_active_index": "true",
            "corpus_id": manifest["corpus_id"],
            "source_directory": manifest["index_dir"],
            "document_count": str(manifest["document_count"]),
            "chunk_count": str(manifest["chunk_count"]),
            "indexed_at": str(manifest["indexed_at"]),
        }
        return build_ok_response("index-status", payload)

    def rag_search(self, query: str, mode: str, top_k: int = 5) -> str:
        try:
            payload = self.retrieval.search(query=query, mode=mode, top_k=top_k)
            xml_payload = {
                "query": payload["query"],
                "mode": payload["mode"],
                "top_k": str(payload["top_k"]),
                "result_count": str(payload["result_count"]),
                "results": payload["results"],
            }
            return build_ok_response("search-results", xml_payload)
        except ServiceException as exc:
            return self._error_to_xml(exc)

    def rag_read_resource(self, uri: str) -> str:
        try:
            payload = self.resources.read(uri)
            return build_ok_response("resource", payload)
        except ServiceException as exc:
            return self._error_to_xml(exc)

    def _error_to_xml(self, exc: ServiceException) -> str:
        return build_error_response(
            code=exc.error.code,
            message=exc.error.message,
            hint=exc.error.hint,
            details=exc.error.details,
        )


def run_stdio_loop(server: StdioServer) -> None:
    for line in sys.stdin:
        raw = line.strip()
        if not raw:
            continue
        request = json.loads(raw)
        tool = request.get("tool")
        args: dict[str, Any] = request.get("args", {})

        if tool == "rag_rebuild_index":
            response = server.rag_rebuild_index(args["directory_path"])
        elif tool == "rag_index_status":
            response = server.rag_index_status()
        elif tool == "rag_search":
            response = server.rag_search(
                query=args["query"],
                mode=args["mode"],
                top_k=int(args.get("top_k", 5)),
            )
        elif tool == "rag_read_resource":
            response = server.rag_read_resource(args["uri"])
        else:
            response = build_error_response(
                code=ErrorCode.UNSUPPORTED_SEARCH_MODE,
                message=f"未知工具: {tool}",
                hint="请使用 rag_rebuild_index/rag_index_status/rag_search/rag_read_resource",
            )
        sys.stdout.write(response + "\n")
        sys.stdout.flush()


def main() -> None:
    server = StdioServer()
    run_stdio_loop(server)


if __name__ == "__main__":
    main()
