from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from rag_mcp.config import AppConfig


class ApiReranker:
    """Calls a Cohere-compatible /rerank endpoint (e.g. SiliconFlow)."""

    def __init__(self, api_key: str, base_url: str, model: str, timeout: int = 30) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def rerank(self, query: str, candidates: list[dict]) -> list[dict]:
        if not candidates:
            return []
        documents = [c["text"] for c in candidates]
        resp = httpx.post(
            f"{self.base_url}/rerank",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={"model": self.model, "query": query, "documents": documents},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        results = resp.json()["results"]
        # results: [{"index": int, "relevance_score": float}, ...] sorted by score desc
        return [
            {**candidates[r["index"]], "score": r["relevance_score"]}
            for r in results
        ]


def build_reranker(cfg: "AppConfig") -> Any | None:
    if not cfg.rerank_api_key.strip():
        return None
    return ApiReranker(
        api_key=cfg.rerank_api_key,
        base_url=cfg.rerank_base_url,
        model=cfg.rerank_model,
        timeout=cfg.rerank_timeout_seconds,
    )
