from __future__ import annotations

import re
from dataclasses import dataclass


URI_PATTERN = re.compile(
    r"^rag://corpus/(?P<corpus_id>[a-zA-Z0-9]+)/(?P<doc_id>[a-zA-Z0-9]+)#chunk-(?P<chunk_index>\d+)$"
)


@dataclass(frozen=True)
class ParsedRagUri:
    corpus_id: str
    doc_id: str
    chunk_index: int


def parse_rag_uri(uri: str) -> ParsedRagUri:
    match = URI_PATTERN.match(uri)
    if match is None:
        raise ValueError(f"invalid rag uri: {uri}")
    return ParsedRagUri(
        corpus_id=match.group("corpus_id"),
        doc_id=match.group("doc_id"),
        chunk_index=int(match.group("chunk_index")),
    )

