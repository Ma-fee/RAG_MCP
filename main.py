from rag_mcp.config import AppConfig
from rag_mcp.transport.http_server import run_http_server
from rag_mcp.transport.stdio_server import main as run_stdio_server


def main() -> None:
    cfg = AppConfig.from_env()
    if cfg.enable_http:
        run_http_server(data_dir=cfg.data_dir, host=cfg.http_host, port=cfg.http_port)
        return
    run_stdio_server()


if __name__ == "__main__":
    main()
