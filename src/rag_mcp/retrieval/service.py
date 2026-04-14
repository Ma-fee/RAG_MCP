from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from openai import OpenAI

from rag_mcp.errors import ErrorCode, ServiceError, ServiceException
from rag_mcp.indexing.keyword_index import KeywordIndex
from rag_mcp.indexing.manifest import read_active_manifest
from rag_mcp.indexing.vector_index import VectorIndex


class RetrievalService:
    def __init__(
        self,
        data_dir: Path,
        embedding_provider: Any | None = None,
        reranker: Any | None = None,
        rerank_top_k_candidates: int = 20,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.embedding_provider = embedding_provider
        self._reranker = reranker
        self._rerank_top_k_candidates = rerank_top_k_candidates

    def search(
        self,
        query: str,
        top_k: int = 5,
    ) -> dict[str, Any]:
        return self._search_hybrid_rerank(query=query, top_k=top_k)

    def _search_keyword(self, query: str, top_k: int) -> dict[str, Any]:
        manifest = self._load_active_manifest()
        keyword_index = KeywordIndex.load(Path(manifest["index_dir"]))
        raw_hits = keyword_index.search(query, top_k=top_k)
        results = [
            {
                "text": hit["text"],
                "title": hit["title"],
                "uri": hit["uri"],
                "score": hit["score"],
                "metadata": hit["metadata"],
            }
            for hit in raw_hits
        ]
        return {
            "query": query,
            "mode": "keyword",
            "top_k": top_k,
            "result_count": len(results),
            "results": results,
        }

    def _search_vector(self, query: str, top_k: int) -> dict[str, Any]:
        manifest = self._load_active_manifest()
        if self.embedding_provider is None:
            return {
                "query": query,
                "mode": "vector",
                "top_k": top_k,
                "result_count": 0,
                "results": [],
            }

        index_dir = Path(manifest["index_dir"])
        if not (index_dir / "chroma").exists():
            return {
                "query": query,
                "mode": "vector",
                "top_k": top_k,
                "result_count": 0,
                "results": [],
            }

        vector_index = VectorIndex(index_dir=index_dir)
        query_embedding = self.embedding_provider.embed_query(query)
        raw_hits = vector_index.search_by_vector(query_embedding, top_k=top_k)
        results = [
            {
                "text": hit["text"],
                "title": hit.get("title", ""),
                "uri": hit["uri"],
                "score": hit.get("score", 0.0),
                "metadata": hit.get("metadata", {}),
            }
            for hit in raw_hits
        ]
        return {
            "query": query,
            "mode": "vector",
            "top_k": top_k,
            "result_count": len(results),
            "results": results,
        }

    def _load_active_manifest(self) -> dict[str, Any]:
        manifest = read_active_manifest(self.data_dir / "active_index.json")
        if manifest is None:
            raise ServiceException(
                ServiceError(
                    code=ErrorCode.NO_ACTIVE_INDEX,
                    message="当前没有活动索引",
                    hint="请先调用 rag_rebuild_index",
                )
            )
        return manifest

    def _search_hybrid_rerank(self, query: str, top_k: int) -> dict[str, Any]:
        split_queries = self._split_query_intent(query)
        keyword_query = split_queries["keyword_query"]
        vector_query = split_queries["vector_query"]

        candidate_k = max(self._rerank_top_k_candidates, top_k * 4)
        keyword_hits = self._search_keyword(query=keyword_query, top_k=candidate_k)
        vector_hits = self._search_vector(query=vector_query, top_k=candidate_k)

        fused_candidates = self._rrf_fuse(
            keyword_results=keyword_hits["results"],
            vector_results=vector_hits["results"],
            top_k=candidate_k,
        )

        if self._reranker is None:
            results = fused_candidates[:top_k]
        else:
            reranked = self._reranker.rerank(query=query, candidates=fused_candidates)
            results = reranked[:top_k]

        return {
            "query": query,
            "mode": "hybrid_rerank",
            "top_k": top_k,
            "subqueries": split_queries,
            "keyword_result_count": keyword_hits["result_count"],
            "vector_result_count": vector_hits["result_count"],
            "fused_candidate_count": len(fused_candidates),
            "result_count": len(results),
            "results": results,
        }

    def _rrf_fuse(
        self,
        keyword_results: list[dict[str, Any]],
        vector_results: list[dict[str, Any]],
        top_k: int,
    ) -> list[dict[str, Any]]:
        rrf_k = 60
        score_by_uri: dict[str, float] = {}
        item_by_uri: dict[str, dict[str, Any]] = {}

        for rank, item in enumerate(keyword_results):
            uri = str(item.get("uri", ""))
            if not uri:
                continue
            score_by_uri[uri] = score_by_uri.get(uri, 0.0) + 1.0 / (rrf_k + rank + 1)
            item_by_uri[uri] = item

        for rank, item in enumerate(vector_results):
            uri = str(item.get("uri", ""))
            if not uri:
                continue
            score_by_uri[uri] = score_by_uri.get(uri, 0.0) + 1.0 / (rrf_k + rank + 1)
            if uri not in item_by_uri:
                item_by_uri[uri] = item

        ranked_uris = sorted(
            score_by_uri.keys(), key=lambda u: score_by_uri[u], reverse=True
        )[:top_k]
        fused: list[dict[str, Any]] = []
        for uri in ranked_uris:
            payload = dict(item_by_uri[uri])
            payload["score"] = score_by_uri[uri]
            fused.append(payload)
        return fused

    def _split_query_intent(self, query: str) -> dict[str, str]:
        splitter_api_key = os.getenv("QUERY_SPLITTER_API_KEY", "").strip()
        splitter_base_url = os.getenv("QUERY_SPLITTER_BASE_URL", "").strip()
        splitter_model = os.getenv("QUERY_SPLITTER_MODEL", "").strip()

        if splitter_api_key and splitter_base_url and splitter_model:
            parsed = self._split_query_with_llm(
                query=query,
                api_key=splitter_api_key,
                base_url=splitter_base_url,
                model=splitter_model,
            )
            if parsed is not None:
                return parsed

        # Heuristic fallback when lightweight LLM splitter is unavailable.
        normalized = " ".join(query.strip().split())
        keyword_query = normalized
        vector_query = normalized
        return {"keyword_query": keyword_query, "vector_query": vector_query}

    def _split_query_with_llm(
        self,
        query: str,
        api_key: str,
        base_url: str,
        model: str,
    ) -> dict[str, str] | None:
        prompt = (
            "You are a query planner for hybrid retrieval. "
            "Split user query into two subqueries:\n"
            "1) keyword_query: concise terms for exact lexical matching\n"
            "2) vector_query: semantically complete phrase for embedding retrieval\n"
            "Return JSON only with keys keyword_query and vector_query."
        )
        try:
            client = OpenAI(api_key=api_key, base_url=base_url)
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": query},
                ],
                temperature=0,
                stream=False,
            )
            content = response.choices[0].message.content
            if not content:
                return None
            json_text = self._extract_json_object(content)
            if not json_text:
                return None
            data = json.loads(json_text)
            keyword_query = str(data.get("keyword_query", "")).strip()
            vector_query = str(data.get("vector_query", "")).strip()
            if not keyword_query or not vector_query:
                return None
            return {
                "keyword_query": keyword_query,
                "vector_query": vector_query,
            }
        except Exception:
            return None

    def _extract_json_object(self, text: str) -> str:
        stripped = text.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            return stripped
        match = re.search(r"\{[\s\S]*\}", stripped)
        if match:
            return match.group(0)
        return ""
