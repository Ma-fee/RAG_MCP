from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SearchHit:
    uri: str
    text: str
    title: str
    score: float
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "uri": self.uri,
            "text": self.text,
            "title": self.title,
            "score": self.score,
            "metadata": self.metadata,
        }
