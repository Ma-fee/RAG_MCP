from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9_]+")


@dataclass
class KeywordIndex:
    corpus_id: str
    entries: list[dict[str, Any]]

    @classmethod
    def load(cls, index_dir: Path) -> "KeywordIndex":
        data = json.loads((index_dir / "keyword_store.json").read_text(encoding="utf-8"))
        return cls(corpus_id=data["corpus_id"], entries=data["entries"])

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        query_tokens = _tokenize(query)
        scored: list[tuple[float, dict[str, Any]]] = []
        for entry in self.entries:
            text_tokens = _tokenize(entry["text"])
            score = _overlap_score(query_tokens, text_tokens)
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
    payload = {"corpus_id": corpus_id, "entries": entries}
    (index_dir / "keyword_store.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _tokenize(text: str) -> set[str]:
    return {token.lower() for token in TOKEN_PATTERN.findall(text)}


def _overlap_score(query_tokens: set[str], text_tokens: set[str]) -> float:
    if not query_tokens or not text_tokens:
        return 0.0
    overlap = len(query_tokens.intersection(text_tokens))
    return float(overlap) / float(len(query_tokens))

