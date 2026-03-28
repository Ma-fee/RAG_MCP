from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chromadb


@dataclass
class VectorIndex:
    index_dir: Path
    collection_name: str = "chunks"

    def __post_init__(self) -> None:
        self.index_dir = Path(self.index_dir)
        self._persist_dir = self.index_dir / "chroma"
        self._persist_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(self._persist_dir))
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def reset(self) -> None:
        try:
            self._client.delete_collection(self.collection_name)
        except Exception:
            pass
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert_chunks(
        self, entries: list[dict[str, Any]], embeddings: list[list[float]]
    ) -> None:
        if len(entries) != len(embeddings):
            raise ValueError("entries and embeddings length mismatch")
        if not entries:
            return

        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict[str, Any]] = []
        for entry in entries:
            ids.append(entry["id"])
            documents.append(entry["text"])
            metadatas.append(
                {
                    "payload_json": json.dumps(
                        {
                            "id": entry["id"],
                            "text": entry["text"],
                            "uri": entry["uri"],
                            "title": entry["title"],
                            "metadata": entry["metadata"],
                        },
                        ensure_ascii=False,
                    )
                }
            )

        self._collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings,
        )

    def search_by_vector(
        self, query_embedding: list[float], top_k: int = 5
    ) -> list[dict[str, Any]]:
        result = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["metadatas", "distances"],
        )
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]

        hits: list[dict[str, Any]] = []
        for meta, distance in zip(metadatas, distances):
            payload = json.loads(meta["payload_json"])
            payload["score"] = float(1.0 - float(distance))
            hits.append(payload)
        return hits

