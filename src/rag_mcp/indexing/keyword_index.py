from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

TOKEN_PATTERN = re.compile(r"\w+")

_BM25_K1 = 1.5
_BM25_B = 0.75


class KeywordIndex:
    def __init__(
        self,
        entries: list[dict[str, Any]],
        idf: dict[str, float] | None = None,
        avgdl: float | None = None,
    ) -> None:
        self.entries = entries
        self._idf = idf or {}
        self._avgdl = avgdl

    @classmethod
    def load(cls, index_dir: Path) -> "KeywordIndex":
        payload = json.loads((index_dir / "keyword_store.json").read_text(encoding="utf-8"))
        idf = payload.get("idf")
        avgdl = payload.get("avgdl")
        instance = cls(payload["entries"], idf=idf, avgdl=avgdl)
        if not idf or avgdl is None:
            instance._idf, instance._avgdl = _compute_bm25_stats(payload["entries"])
        return instance

    def search(self, query: str, top_k: int = 10) -> list[dict[str, Any]]:
        query_tokens = _tokenize_list(query)
        if not query_tokens:
            return []
        scored: list[tuple[float, dict[str, Any]]] = []
        for entry in self.entries:
            score = _bm25_score(query_tokens, entry["text"], self._idf, self._avgdl or 1.0)
            if score <= 0:
                continue
            candidate = dict(entry)
            candidate["score"] = score
            scored.append((score, candidate))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [item[1] for item in scored[:top_k]]


def persist_keyword_store(
    index_dir: Path, corpus_id: str, entries: list[dict[str, Any]]
) -> None:
    index_dir.mkdir(parents=True, exist_ok=True)
    idf, avgdl = _compute_bm25_stats(entries)
    payload = {
        "corpus_id": corpus_id,
        "avgdl": avgdl,
        "idf": idf,
        "entries": entries,
    }
    (index_dir / "keyword_store.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _compute_bm25_stats(entries: list[dict[str, Any]]) -> tuple[dict[str, float], float]:
    N = len(entries)
    if N == 0:
        return {}, 1.0
    df: dict[str, int] = {}
    lengths: list[int] = []
    for entry in entries:
        tokens = _tokenize_list(entry.get("text", ""))
        lengths.append(len(tokens))
        for term in set(tokens):
            df[term] = df.get(term, 0) + 1
    avgdl = sum(lengths) / N if lengths else 1.0
    idf = {
        term: math.log((N - freq + 0.5) / (freq + 0.5) + 1.0)
        for term, freq in df.items()
    }
    return idf, avgdl


def _bm25_score(
    query_tokens: list[str],
    doc_text: str,
    idf: dict[str, float],
    avgdl: float,
) -> float:
    doc_tokens = _tokenize_list(doc_text)
    dl = len(doc_tokens)
    if dl == 0:
        return 0.0
    tf_map: dict[str, int] = {}
    for t in doc_tokens:
        tf_map[t] = tf_map.get(t, 0) + 1
    score = 0.0
    for term in query_tokens:
        if term not in tf_map:
            continue
        tf = tf_map[term]
        term_idf = idf.get(term, math.log((1.0 + 0.5) / (1 + 0.5) + 1.0))
        numerator = tf * (_BM25_K1 + 1)
        denominator = tf + _BM25_K1 * (1 - _BM25_B + _BM25_B * dl / avgdl)
        score += term_idf * (numerator / denominator)
    return score


def _tokenize(text: str) -> set[str]:
    return {token.lower() for token in TOKEN_PATTERN.findall(text)}


def _tokenize_list(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_PATTERN.findall(text)]
