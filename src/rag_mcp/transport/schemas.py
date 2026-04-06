from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError, field_validator

from rag_mcp.errors import ErrorCode, ServiceError, ServiceException

T = TypeVar("T", bound=BaseModel)


def _require_non_empty(value: str, *, field: str) -> str:
    normalized = value.strip() if isinstance(value, str) else ""
    if not normalized:
        raise ValueError(f"{field} 不能为空")
    return normalized


def parse_input(model: type[T], payload: dict[str, Any]) -> T:
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        first = exc.errors()[0] if exc.errors() else {}
        ctx = first.get("ctx") or {}
        root_error = ctx.get("error")
        message = str(root_error) if root_error else first.get("msg", "参数校验失败")
        raise ServiceException(
            ServiceError(
                code=ErrorCode.INVALID_ARGUMENT,
                message=message,
                hint="请检查输入参数",
            )
        ) from exc


class SearchInput(BaseModel):
    query: str
    top_k: int | None = 5
    mode: str | None = None

    @field_validator("query")
    @classmethod
    def _normalize_query(cls, value: str) -> str:
        return _require_non_empty(value, field="query")

    @field_validator("top_k")
    @classmethod
    def _normalize_top_k(cls, value: int | None) -> int:
        if value is None:
            return 5
        if value < 1:
            raise ValueError("top_k 必须大于等于 1")
        return value


class ReadResourceInput(BaseModel):
    uri: str

    @field_validator("uri")
    @classmethod
    def _normalize_uri(cls, value: str) -> str:
        return _require_non_empty(value, field="uri")


class ListSectionsInput(BaseModel):
    filename: str

    @field_validator("filename")
    @classmethod
    def _normalize_filename(cls, value: str) -> str:
        return _require_non_empty(value, field="filename")


class SectionRetrievalInput(BaseModel):
    title: list[str]
    filename: str
    description: str = ""
    top_k: int | None = 10

    @field_validator("filename")
    @classmethod
    def _normalize_filename(cls, value: str) -> str:
        return _require_non_empty(value, field="filename")

    @field_validator("title")
    @classmethod
    def _normalize_title(cls, values: list[str]) -> list[str]:
        normalized = [
            item.strip() for item in values if isinstance(item, str) and item.strip()
        ]
        if not normalized:
            raise ValueError("title 不能为空")
        return normalized

    @field_validator("top_k")
    @classmethod
    def _normalize_top_k(cls, value: int | None) -> int:
        if value is None:
            return 10
        if value < 1:
            raise ValueError("top_k 必须大于等于 1")
        return value
