from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib import request

from rag_mcp.config import AppConfig


@dataclass
class EmbeddingClient:
    base_url: str
    api_key: str
    model: str
    timeout_seconds: int
    dimension: int | None

    @classmethod
    def from_config(cls, cfg: AppConfig) -> "EmbeddingClient":
        api_key = cfg.embedding_api_key.strip()
        if not api_key:
            raise ValueError("EMBEDDING_API_KEY is required")

        model = cfg.embedding_model.strip()
        if not model:
            raise ValueError("EMBEDDING_MODEL is required")

        if cfg.embedding_timeout_seconds <= 0:
            raise ValueError("EMBEDDING_TIMEOUT_SECONDS must be > 0")

        return cls(
            base_url=cfg.embedding_base_url.rstrip("/"),
            api_key=api_key,
            model=model,
            timeout_seconds=cfg.embedding_timeout_seconds,
            dimension=cfg.embedding_dimension,
        )

    def model_name(self) -> str:
        return self.model

    def embedding_dimension(self) -> int | None:
        return self.dimension

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        payload = {"model": self.model, "input": texts}
        response = self._post_embeddings(payload)
        return [item["embedding"] for item in response["data"]]

    def embed_query(self, text: str) -> list[float]:
        payload = {"model": self.model, "input": text}
        response = self._post_embeddings(payload)
        return response["data"][0]["embedding"]

    def _post_embeddings(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url=f"{self.base_url}/embeddings",
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with request.urlopen(req, timeout=self.timeout_seconds) as resp:
            raw = resp.read().decode("utf-8")
        return json.loads(raw)

