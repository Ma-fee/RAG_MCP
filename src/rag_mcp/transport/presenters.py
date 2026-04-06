from __future__ import annotations

from typing import Any

from rag_mcp.errors import ErrorCode, ServiceException


def error_from_service(exc: ServiceException) -> dict[str, str]:
    return {"error": exc.error.code.value, "message": exc.error.message}


def error_from_internal(
    message: str = "内部服务异常，请稍后重试",
    *,
    code: ErrorCode = ErrorCode.INTERNAL_ERROR,
) -> dict[str, str]:
    return {"error": code.value, "message": message}


def success_list(*, items: list[dict[str, Any]], key: str = "results") -> dict[str, Any]:
    return {"count": len(items), key: items}


def success_query(
    *,
    query: str,
    results: list[dict[str, Any]],
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "query": query,
        "result_count": len(results),
        "results": results,
    }
    if extra:
        payload.update(extra)
    return payload
