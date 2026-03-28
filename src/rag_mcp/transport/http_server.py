from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from rag_mcp.transport.handlers import ToolHandlers


class HttpTransportServer:
    def __init__(
        self,
        data_dir: Path,
        host: str = "127.0.0.1",
        port: int = 8787,
        embedding_provider: Any | None = None,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.host = host
        self.embedding_provider = embedding_provider
        self.handlers = ToolHandlers(
            data_dir=self.data_dir, embedding_provider=self.embedding_provider
        )

        handler_cls = self._build_handler_class()
        self._server = ThreadingHTTPServer((self.host, int(port)), handler_cls)
        self.port = int(self._server.server_port)
        self._thread: threading.Thread | None = None

    def _build_handler_class(self) -> type[BaseHTTPRequestHandler]:
        outer = self

        class _Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                if self.path != "/tool":
                    self.send_response(404)
                    self.end_headers()
                    return
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length).decode("utf-8")
                payload = json.loads(raw or "{}")
                tool = str(payload.get("tool", ""))
                args = payload.get("args", {})
                if not isinstance(args, dict):
                    args = {}
                xml_text = outer.handlers.handle_tool(tool=tool, args=args)
                data = xml_text.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/xml; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, format: str, *args: object) -> None:
                return

        return _Handler

    def endpoint_url(self) -> str:
        return f"http://{self.host}:{self.port}/tool"

    def serve_forever(self) -> None:
        self._server.serve_forever()

    def start_background(self) -> "HttpTransportServer":
        if self._thread is not None and self._thread.is_alive():
            return self
        self._thread = threading.Thread(target=self.serve_forever, daemon=True)
        self._thread.start()
        return self

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2)


def start_http_server_if_enabled(
    enable_http: bool,
    data_dir: Path,
    host: str = "127.0.0.1",
    port: int = 8787,
    embedding_provider: Any | None = None,
) -> HttpTransportServer | None:
    if not enable_http:
        return None
    return HttpTransportServer(
        data_dir=data_dir,
        host=host,
        port=port,
        embedding_provider=embedding_provider,
    ).start_background()


def run_http_server(
    data_dir: Path,
    host: str = "127.0.0.1",
    port: int = 8787,
    embedding_provider: Any | None = None,
) -> None:
    server = HttpTransportServer(
        data_dir=data_dir,
        host=host,
        port=port,
        embedding_provider=embedding_provider,
    )
    server.serve_forever()
