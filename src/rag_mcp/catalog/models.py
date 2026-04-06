from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SectionResult:
    uri: str
    title: str
    text: str
    metadata: dict[str, Any]
    related_resource_uris: list[str]
    related_resources: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "uri": self.uri,
            "title": self.title,
            "text": self.text,
            "metadata": self.metadata,
            "related_resource_uris": self.related_resource_uris,
            "related_resources": self.related_resources,
        }
