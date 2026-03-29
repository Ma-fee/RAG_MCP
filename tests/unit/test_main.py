from __future__ import annotations

import importlib.util
from pathlib import Path

from rag_mcp.config import AppConfig

_MAIN_PATH = Path(__file__).resolve().parents[2] / "main.py"
_SPEC = importlib.util.spec_from_file_location("repo_main", _MAIN_PATH)
assert _SPEC is not None and _SPEC.loader is not None
app_main = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(app_main)


def _make_cfg(enable_http: bool, embedding_api_key: str) -> AppConfig:
    return AppConfig(
        data_dir=Path(".rag_mcp_data"),
        enable_http=enable_http,
        http_host="127.0.0.1",
        http_port=8787,
        embedding_api_key=embedding_api_key,
        embedding_base_url="https://api.siliconflow.cn/v1",
        embedding_model="Qwen/Qwen3-Embedding-0.6B",
        embedding_dimension=None,
        embedding_timeout_seconds=30,
        default_top_k=5,
        keyword_top_k=8,
        chunk_size=800,
        chunk_overlap=120,
        multimodal_api_key="",
        multimodal_base_url="https://api.siliconflow.cn/v1",
        multimodal_model="zai-org/GLM-4.6V",
    )


def test_build_embedding_provider_returns_none_without_api_key() -> None:
    cfg = _make_cfg(enable_http=False, embedding_api_key="")
    assert app_main._build_embedding_provider(cfg) is None


def test_build_embedding_provider_uses_embedding_client(monkeypatch) -> None:
    cfg = _make_cfg(enable_http=False, embedding_api_key="sk-test")
    sentinel = object()

    monkeypatch.setattr(
        app_main.EmbeddingClient,
        "from_config",
        lambda got_cfg: sentinel if got_cfg == cfg else None,
    )

    assert app_main._build_embedding_provider(cfg) is sentinel


def test_main_runs_stdio_loop_when_http_disabled(monkeypatch) -> None:
    cfg = _make_cfg(enable_http=False, embedding_api_key="sk-test")
    sentinel_provider = object()
    captured: dict[str, object] = {}

    monkeypatch.setattr(app_main.AppConfig, "from_env", lambda: cfg)
    monkeypatch.setattr(app_main, "_build_embedding_provider", lambda _cfg: sentinel_provider)

    class _FakeStdioServer:
        def __init__(self, data_dir: Path, embedding_provider: object) -> None:
            captured["data_dir"] = data_dir
            captured["embedding_provider"] = embedding_provider

    monkeypatch.setattr(app_main, "StdioServer", _FakeStdioServer)
    monkeypatch.setattr(app_main, "run_stdio_loop", lambda server: captured.setdefault("server", server))

    app_main.main()

    assert captured["data_dir"] == cfg.data_dir
    assert captured["embedding_provider"] is sentinel_provider
    assert captured["server"].__class__.__name__ == "_FakeStdioServer"


def test_main_runs_http_server_when_enabled(monkeypatch) -> None:
    cfg = _make_cfg(enable_http=True, embedding_api_key="sk-test")
    sentinel_provider = object()
    captured: dict[str, object] = {}

    monkeypatch.setattr(app_main.AppConfig, "from_env", lambda: cfg)
    monkeypatch.setattr(app_main, "_build_embedding_provider", lambda _cfg: sentinel_provider)
    monkeypatch.setattr(
        app_main,
        "run_http_server",
        lambda data_dir, host, port, embedding_provider: captured.update(
            {
                "data_dir": data_dir,
                "host": host,
                "port": port,
                "embedding_provider": embedding_provider,
            }
        ),
    )

    app_main.main()

    assert captured["data_dir"] == cfg.data_dir
    assert captured["host"] == cfg.http_host
    assert captured["port"] == cfg.http_port
    assert captured["embedding_provider"] is sentinel_provider
