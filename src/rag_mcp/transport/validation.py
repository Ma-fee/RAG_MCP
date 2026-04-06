from __future__ import annotations

from rag_mcp.errors import ErrorCode, ServiceError, ServiceException


def require_non_empty_string(value: str, *, field: str) -> str:
    normalized = value.strip() if isinstance(value, str) else ""
    if not normalized:
        raise ServiceException(
            ServiceError(
                code=ErrorCode.INVALID_ARGUMENT,
                message=f"{field} 不能为空",
                hint=f"请传入非空 {field}",
            )
        )
    return normalized


def require_non_empty_string_list(values: list[str], *, field: str) -> list[str]:
    normalized = [
        item.strip() for item in values if isinstance(item, str) and item.strip()
    ]
    if not normalized:
        raise ServiceException(
            ServiceError(
                code=ErrorCode.INVALID_ARGUMENT,
                message=f"{field} 不能为空",
                hint=f"请传入非空 {field}",
            )
        )
    return normalized


def normalize_top_k(value: int | None, *, default: int, minimum: int = 1) -> int:
    if value is None:
        return default
    if value < minimum:
        raise ServiceException(
            ServiceError(
                code=ErrorCode.INVALID_ARGUMENT,
                message=f"top_k 必须大于等于 {minimum}",
                hint="请传入合法 top_k 参数",
            )
        )
    return value
