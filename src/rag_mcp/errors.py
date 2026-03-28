from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ErrorCode(str, Enum):
    NO_ACTIVE_INDEX = "NO_ACTIVE_INDEX"
    UNSUPPORTED_SEARCH_MODE = "UNSUPPORTED_SEARCH_MODE"
    SEARCH_MODE_NOT_IMPLEMENTED = "SEARCH_MODE_NOT_IMPLEMENTED"


@dataclass(frozen=True)
class ServiceError:
    code: ErrorCode
    message: str
    hint: str
    details: Optional[dict[str, str]] = None

