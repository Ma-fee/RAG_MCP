from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class RepositoryError(RuntimeError):
    """Base repository error."""


class RepositoryNotFoundError(RepositoryError):
    """Raised when a repository backing file does not exist."""


class RepositoryFormatError(RepositoryError):
    """Raised when a repository backing file has an invalid JSON shape."""


def _read_json_dict(path: Path) -> dict[str, Any]:
    try:
        exists = path.exists()
    except (PermissionError, OSError) as exc:
        raise RepositoryError(f"Unable to access repository file: {path}") from exc
    if not exists:
        raise RepositoryNotFoundError(f"Repository file not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (IsADirectoryError, PermissionError, OSError) as exc:
        raise RepositoryError(f"Unable to read repository file: {path}") from exc
    except UnicodeDecodeError as exc:
        raise RepositoryFormatError(
            f"Repository file is not valid UTF-8 text: {path}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise RepositoryFormatError(f"Invalid JSON in repository file: {path}") from exc
    if not isinstance(payload, dict):
        raise RepositoryFormatError(f"Repository JSON must be an object: {path}")
    return payload


@dataclass
class ActiveIndexRepository:
    data_dir: Path

    def load(self) -> dict[str, Any]:
        payload = _read_json_dict(self.data_dir / "active_index.json")
        required_fields = {
            "corpus_id",
            "index_dir",
            "indexed_at",
            "document_count",
            "chunk_count",
        }
        missing_fields = sorted(required_fields - payload.keys())
        if missing_fields:
            raise RepositoryFormatError(
                f"active_index.json missing required fields: {', '.join(missing_fields)}"
            )
        return payload


@dataclass
class KeywordStoreRepository:
    index_dir: Path
    _payload: dict[str, Any] | None = field(default=None, init=False, repr=False)

    def load(self) -> dict[str, Any]:
        payload = _read_json_dict(self.index_dir / "keyword_store.json")
        entries = payload.get("entries")
        if not isinstance(entries, list):
            raise RepositoryFormatError("keyword_store.json must contain a list field: entries")
        if not all(isinstance(entry, dict) for entry in entries):
            raise RepositoryFormatError(
                "keyword_store.json entries must contain only object items"
            )
        self._payload = payload
        return payload

    def entries(self) -> list[Any]:
        if self._payload is None:
            self.load()
        assert self._payload is not None
        return self._payload["entries"]


@dataclass
class ResourceStoreRepository:
    index_dir: Path
    _payload: dict[str, Any] | None = field(default=None, init=False, repr=False)

    def load(self) -> dict[str, Any]:
        payload = _read_json_dict(self.index_dir / "resource_store.json")
        entries = payload.get("entries")
        if not isinstance(entries, list):
            raise RepositoryFormatError("resource_store.json must contain a list field: entries")
        if not all(isinstance(entry, dict) for entry in entries):
            raise RepositoryFormatError(
                "resource_store.json entries must contain only object items"
            )
        self._payload = payload
        return payload

    def entries(self) -> list[Any]:
        if self._payload is None:
            self.load()
        assert self._payload is not None
        return self._payload["entries"]

    def get(self, uri: str) -> dict[str, Any] | None:
        for entry in self.entries():
            if isinstance(entry, dict) and entry.get("uri") == uri:
                return entry
        return None


@dataclass
class SectionsMappingRepository:
    index_dir: Path

    def load(self) -> dict[str, Any]:
        payload = _read_json_dict(self.index_dir / "sections_mapping.json")
        for value in payload.values():
            if not isinstance(value, list):
                raise RepositoryFormatError(
                    "sections_mapping.json values must all be lists"
                )
        return payload
