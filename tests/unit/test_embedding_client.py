from __future__ import annotations

import pytest

from rag_mcp.config import AppConfig
from rag_mcp.embedding.client import EmbeddingClient


def test_embedding_client_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EMBEDDING_API_KEY", raising=False)
    monkeypatch.setenv("EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-0.6B")

    cfg = AppConfig.from_env()
    with pytest.raises(ValueError, match="EMBEDDING_API_KEY"):
        EmbeddingClient.from_config(cfg)


def test_embedding_client_requires_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMBEDDING_API_KEY", "test-key")
    monkeypatch.setenv("EMBEDDING_MODEL", "")

    cfg = AppConfig.from_env()
    with pytest.raises(ValueError, match="EMBEDDING_MODEL"):
        EmbeddingClient.from_config(cfg)


def test_embedding_client_requires_positive_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EMBEDDING_API_KEY", "test-key")
    monkeypatch.setenv("EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-0.6B")
    monkeypatch.setenv("EMBEDDING_TIMEOUT_SECONDS", "0")

    cfg = AppConfig.from_env()
    with pytest.raises(ValueError, match="EMBEDDING_TIMEOUT_SECONDS"):
        EmbeddingClient.from_config(cfg)


def test_embedding_client_reads_dimension_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EMBEDDING_API_KEY", "test-key")
    monkeypatch.setenv("EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-0.6B")
    monkeypatch.setenv("EMBEDDING_DIMENSION", "1024")

    cfg = AppConfig.from_env()
    client = EmbeddingClient.from_config(cfg)

    assert client.model_name() == "Qwen/Qwen3-Embedding-0.6B"
    assert client.embedding_dimension() == 1024
