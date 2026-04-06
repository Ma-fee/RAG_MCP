from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TextResourcePayload:
    uri: str
    text: str
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "uri": self.uri,
            "text": self.text,
            "metadata": self.metadata,
        }
