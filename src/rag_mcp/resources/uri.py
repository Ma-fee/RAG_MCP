from __future__ import annotations

import re
from dataclasses import dataclass


# Accepts #chunk-N (legacy), #text-N, #image-N, #table-N
URI_PATTERN = re.compile(
    r"^rag://corpus/(?P<corpus_id>[a-zA-Z0-9]+)/(?P<doc_id>[a-zA-Z0-9]+)"
    r"#(?P<fragment_type>chunk|text|image|table)-(?P<index>\d+)$"
)


@dataclass(frozen=True)
class ParsedRagUri:
    corpus_id: str
    doc_id: str
    fragment_type: str  # "chunk", "text", "image", or "table"
    index: int

    @property
    def chunk_index(self) -> int:
        """Backward-compat alias for text/chunk index."""
        return self.index


def parse_rag_uri(uri: str) -> ParsedRagUri:
    match = URI_PATTERN.match(uri)
    if match is None:
        raise ValueError(f"invalid rag uri: {uri}")
    return ParsedRagUri(
        corpus_id=match.group("corpus_id"),
        doc_id=match.group("doc_id"),
        fragment_type=match.group("fragment_type"),
        index=int(match.group("index")),
    )
