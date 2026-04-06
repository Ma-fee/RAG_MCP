from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ErrorCode(str, Enum):
    NO_ACTIVE_INDEX = "NO_ACTIVE_INDEX"
    UNSUPPORTED_SEARCH_MODE = "UNSUPPORTED_SEARCH_MODE"
    SEARCH_MODE_NOT_IMPLEMENTED = "SEARCH_MODE_NOT_IMPLEMENTED"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    VECTOR_INDEX_CONFIG_MISMATCH = "VECTOR_INDEX_CONFIG_MISMATCH"
    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    INVALID_DIRECTORY = "INVALID_DIRECTORY"
    NO_DOCUMENTS = "NO_DOCUMENTS"
    REBUILD_FAILED = "REBUILD_FAILED"
    SEARCH_FAILED = "SEARCH_FAILED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


@dataclass(frozen=True)
class ServiceError:
    code: ErrorCode
    message: str
    hint: str
    details: Optional[dict[str, str]] = None


class ServiceException(Exception):
    def __init__(self, error: ServiceError) -> None:
        super().__init__(f"{error.code.value}: {error.message}")
        self.error = error
