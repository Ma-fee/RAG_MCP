from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from rag_mcp.config import AppConfig
from rag_mcp.transport.handlers import ToolHandlers


class StdioServer:
    def __init__(
        self, data_dir: Path | None = None, embedding_provider: Any | None = None
    ) -> None:
        cfg = AppConfig.from_env()
        self.data_dir = Path(data_dir) if data_dir is not None else cfg.data_dir
        self.embedding_provider = embedding_provider
        self.handlers = ToolHandlers(
            data_dir=self.data_dir, embedding_provider=self.embedding_provider
        )

    def rag_rebuild_index(self, directory_path: str) -> str:
        return self.handlers.rag_rebuild_index(directory_path)

    def rag_index_status(self) -> str:
        return self.handlers.rag_index_status()

    def rag_search(self, query: str, mode: str, top_k: int = 5) -> str:
        return self.handlers.rag_search(query=query, mode=mode, top_k=top_k)

    def rag_read_resource(self, uri: str) -> str:
        return self.handlers.rag_read_resource(uri)

    def handle_tool(self, tool: str, args: dict[str, Any]) -> str:
        return self.handlers.handle_tool(tool, args)


def run_stdio_loop(server: StdioServer) -> None:
    for line in sys.stdin:
        raw = line.strip()
        if not raw:
            continue
        request = json.loads(raw)
        tool = request.get("tool")
        args: dict[str, Any] = request.get("args", {})

        response = server.handle_tool(tool, args)
        sys.stdout.write(response + "\n")
        sys.stdout.flush()


def main() -> None:
    server = StdioServer()
    run_stdio_loop(server)


if __name__ == "__main__":
    main()
