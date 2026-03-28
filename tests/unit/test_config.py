from __future__ import annotations

from pathlib import Path

import pytest

from rag_mcp.config import AppConfig


@pytest.mark.parametrize(
    ("env_name", "env_value"),
    [
        ("RAG_MCP_DATA_DIR", ".test-data"),
        ("EMBEDDING_BASE_URL", "https://example.com/v1"),
        ("EMBEDDING_MODEL", "fake-embedding-model"),
    ],
)
def test_config_reads_environment_overrides(
    monkeypatch: pytest.MonkeyPatch, env_name: str, env_value: str
) -> None:
    monkeypatch.setenv(env_name, env_value)

    cfg = AppConfig.from_env()

    if env_name == "RAG_MCP_DATA_DIR":
        assert cfg.data_dir == Path(".test-data")
    elif env_name == "EMBEDDING_BASE_URL":
        assert cfg.embedding_base_url == "https://example.com/v1"
    elif env_name == "EMBEDDING_MODEL":
        assert cfg.embedding_model == "fake-embedding-model"


def test_config_uses_rfc_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RAG_MCP_DATA_DIR", raising=False)
    monkeypatch.delenv("EMBEDDING_BASE_URL", raising=False)
    monkeypatch.delenv("EMBEDDING_MODEL", raising=False)
    monkeypatch.delenv("DEFAULT_TOP_K", raising=False)
    monkeypatch.delenv("KEYWORD_TOP_K", raising=False)
    monkeypatch.delenv("CHUNK_SIZE", raising=False)
    monkeypatch.delenv("CHUNK_OVERLAP", raising=False)

    cfg = AppConfig.from_env()

    assert cfg.data_dir == Path(".rag_mcp_data")
    assert cfg.embedding_base_url == "https://api.siliconflow.cn/v1"
    assert cfg.embedding_model == "Qwen/Qwen3-Embedding-0.6B"
    assert cfg.default_top_k == 5
    assert cfg.keyword_top_k == 8
    assert cfg.chunk_size == 800
    assert cfg.chunk_overlap == 120
