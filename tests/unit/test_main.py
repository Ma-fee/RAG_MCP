from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

from rag_mcp.config import AppConfig

_MAIN_PATH = Path(__file__).resolve().parents[2] / "main.py"
_SPEC = importlib.util.spec_from_file_location("repo_main", _MAIN_PATH)
assert _SPEC is not None and _SPEC.loader is not None
app_main = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(app_main)


def _make_cfg(mcp_transport: str = "stdio", embedding_api_key: str = "") -> AppConfig:
    return AppConfig(
        data_dir=Path(".rag_mcp_data"),
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
        mcp_transport=mcp_transport,
        rerank_api_key="",
        rerank_base_url="https://api.siliconflow.cn/v1",
        rerank_model="Qwen/Qwen3-Reranker-0.6B",
        rerank_timeout_seconds=30,
        rerank_top_k_candidates=20,
    )


def test_build_embedding_provider_returns_none_without_api_key() -> None:
    cfg = _make_cfg(embedding_api_key="")
    assert app_main._build_embedding_provider(cfg) is None


def test_build_embedding_provider_uses_embedding_client(monkeypatch) -> None:
    cfg = _make_cfg(embedding_api_key="sk-test")
    sentinel = object()

    monkeypatch.setattr(
        app_main.EmbeddingClient,
        "from_config",
        lambda got_cfg: sentinel if got_cfg == cfg else None,
    )

    assert app_main._build_embedding_provider(cfg) is sentinel


def test_main_stdio_calls_mcp_run(monkeypatch) -> None:
    cfg = _make_cfg(mcp_transport="stdio")
    fake_mcp = MagicMock()
    captured: dict = {}

    monkeypatch.setattr(app_main.AppConfig, "from_env", lambda: cfg)
    monkeypatch.setattr(app_main, "_build_embedding_provider", lambda _cfg: None)
    monkeypatch.setattr(app_main, "create_mcp_server", lambda handlers: fake_mcp)
    fake_mcp.run.side_effect = lambda transport: captured.update({"transport": transport})

    app_main.main()

    fake_mcp.run.assert_called_once_with(transport="stdio")


def test_main_sse_calls_mcp_run(monkeypatch) -> None:
    cfg = _make_cfg(mcp_transport="sse")
    fake_mcp = MagicMock()

    monkeypatch.setattr(app_main.AppConfig, "from_env", lambda: cfg)
    monkeypatch.setattr(app_main, "_build_embedding_provider", lambda _cfg: None)
    monkeypatch.setattr(app_main, "create_mcp_server", lambda handlers: fake_mcp)

    app_main.main()

    fake_mcp.run.assert_called_once_with(transport="sse", host=cfg.http_host, port=cfg.http_port)
