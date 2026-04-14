# Phase 2 Tool Contract Unification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 统一 `rag_mcp` 的 tool error model、成功返回 schema 和参数校验路径，让 MCP tool contract 稳定且可测试。

**Architecture:** service 层继续抛 `ServiceException`；transport 层统一通过 error presenter 和 success presenter 输出 dict；参数校验从散落的 handler 分支条件收口到 validation helper。Phase 2 不重做 indexing/domain 结构。

**Tech Stack:** Python 3.13, pytest, Enum, dataclasses, FastMCP tool dict payloads

---

## 0) Plan Review

- [ ] 已确认本 Phase 不改 `rag://` URI 契约。
- [ ] 已确认本 Phase 不重做 indexing pipeline。
- [ ] 已确认本 Phase 可以统一历史 error literal 为正式 `ErrorCode`。
- [ ] 已确认本 Phase 可以新增 transport helper 文件。
- [ ] Reviewer: Pending
- [ ] Review Date: 2026-04-06

## 1) 文件规划

**Create**
- `src/rag_mcp/transport/presenters.py`
- `src/rag_mcp/transport/validation.py`
- `tests/unit/test_error_contract.py`
- `tests/unit/test_tool_output_contract.py`
- `tests/unit/test_transport_validation.py`
- `docs/tool-contract.md`

**Modify**
- `src/rag_mcp/errors.py`
- `src/rag_mcp/transport/handlers.py`
- `tests/unit/test_handlers_dict.py`
- `README.md`

## 2) 原子化 TDD Tasks

### Task 1: 统一错误码与错误输出

**Files:**
- Modify: `src/rag_mcp/errors.py`
- Modify: `src/rag_mcp/transport/handlers.py`
- Test: `tests/unit/test_error_contract.py`

- [ ] **Step 1: 写失败测试**

```python
def test_handler_maps_service_exception_to_error_dict(tmp_path: Path) -> None:
    handlers = ToolHandlers(data_dir=tmp_path)

    exc = ServiceException(
        ServiceError(
            code=ErrorCode.INVALID_ARGUMENT,
            message="filename 不能为空",
            hint="请传入非空 filename",
        )
    )

    assert handlers._service_error_dict(exc) == {
        "error": "INVALID_ARGUMENT",
        "message": "filename 不能为空",
    }
```

再补：
- 非 `ServiceException` 兜底映射为 `INTERNAL_ERROR`
- `query=""` / `filename=""` 最终错误码统一为 `INVALID_ARGUMENT`

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest -q tests/unit/test_error_contract.py`  
Expected: FAIL。

- [ ] **Step 3: 写最小实现**

```python
class ErrorCode(str, Enum):
    NO_ACTIVE_INDEX = "NO_ACTIVE_INDEX"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    INVALID_DIRECTORY = "INVALID_DIRECTORY"
    NO_DOCUMENTS = "NO_DOCUMENTS"
    REBUILD_FAILED = "REBUILD_FAILED"
    SEARCH_FAILED = "SEARCH_FAILED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
```

```python
def _service_error_dict(self, exc: ServiceException) -> dict[str, str]:
    return {"error": exc.error.code.value, "message": exc.error.message}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest -q tests/unit/test_error_contract.py`  
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add src/rag_mcp/errors.py src/rag_mcp/transport/handlers.py tests/unit/test_error_contract.py
git commit -m "refactor: unify handler error model and transport mapping"
```

### Task 2: 抽 success presenter，统一成功返回 schema

**Files:**
- Create: `src/rag_mcp/transport/presenters.py`
- Modify: `src/rag_mcp/transport/handlers.py`
- Test: `tests/unit/test_tool_output_contract.py`
- Modify/Test: `tests/unit/test_handlers_dict.py`

- [ ] **Step 1: 写失败测试**

```python
def test_success_list_uses_declared_key() -> None:
    payload = success_list(
        items=[{"filename": "doc"}],
        key="filenames",
    )

    assert payload == {
        "count": 1,
        "filenames": [{"filename": "doc"}],
    }
```

```python
def test_success_query_shapes_result_count() -> None:
    payload = success_query(query="hello", results=[{"uri": "rag://x"}])
    assert payload["query"] == "hello"
    assert payload["result_count"] == 1
```

再补 handler 回归：
- `list_filenames` 保持 `count + filenames`
- `section_retrieval` 保持 `requested_section_titles + result_count + results`

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
uv run pytest -q tests/unit/test_tool_output_contract.py
uv run pytest -q tests/unit/test_handlers_dict.py
```

Expected: FAIL。

- [ ] **Step 3: 写最小实现**

```python
def success_list(*, items: list[dict[str, Any]], key: str = "results") -> dict[str, Any]:
    return {"count": len(items), key: items}


def success_query(*, query: str, results: list[dict[str, Any]], extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = {"query": query, "result_count": len(results), "results": results}
    if extra:
        payload.update(extra)
    return payload
```

在 handler 中逐步替换重复的 dict 拼装代码，但不要改现有稳定键名。

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
uv run pytest -q tests/unit/test_tool_output_contract.py
uv run pytest -q tests/unit/test_handlers_dict.py
```

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add src/rag_mcp/transport/presenters.py src/rag_mcp/transport/handlers.py tests/unit/test_tool_output_contract.py tests/unit/test_handlers_dict.py
git commit -m "refactor: standardize tool success payload presenters"
```

### Task 3: 抽 validation helper，统一参数校验

**Files:**
- Create: `src/rag_mcp/transport/validation.py`
- Modify: `src/rag_mcp/transport/handlers.py`
- Test: `tests/unit/test_transport_validation.py`

- [ ] **Step 1: 写失败测试**

```python
def test_require_non_empty_string_rejects_blank() -> None:
    with pytest.raises(ServiceException) as exc:
        require_non_empty_string("   ", field="filename")
    assert exc.value.error.code == ErrorCode.INVALID_ARGUMENT
```

```python
def test_require_non_empty_string_list_rejects_all_blank() -> None:
    with pytest.raises(ServiceException) as exc:
        require_non_empty_string_list(["", "  "], field="section_title")
    assert exc.value.error.code == ErrorCode.INVALID_ARGUMENT
```

再补：
- `normalize_top_k(0, default=5)` 抛 `INVALID_ARGUMENT`

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest -q tests/unit/test_transport_validation.py`  
Expected: FAIL。

- [ ] **Step 3: 写最小实现**

```python
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
```

```python
def require_non_empty_string_list(values: list[str], *, field: str) -> list[str]:
    normalized = [item.strip() for item in values if isinstance(item, str) and item.strip()]
    if not normalized:
        raise ServiceException(
            ServiceError(
                code=ErrorCode.INVALID_ARGUMENT,
                message=f"{field} 不能为空",
                hint=f"请传入非空 {field}",
            )
        )
    return normalized
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest -q tests/unit/test_transport_validation.py`  
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add src/rag_mcp/transport/validation.py src/rag_mcp/transport/handlers.py tests/unit/test_transport_validation.py
git commit -m "refactor: unify transport validation helpers"
```

### Task 4: 固化 tool contract 文档与回归

**Files:**
- Create: `docs/tool-contract.md`
- Modify: `README.md`
- Modify/Test: `tests/unit/test_handlers_dict.py`
- Optional: `tests/integration/test_tool_contract_stability.py`

- [ ] **Step 1: 写失败测试或断言快照**

在 `tests/unit/test_handlers_dict.py` 增加更明确的 contract 断言，例如：

```python
def test_section_retrieval_contract_keys(tmp_path: Path) -> None:
    _write_active_keyword_store(tmp_path)
    result = ToolHandlers(data_dir=tmp_path).section_retrieval(
        section_title=["1.1 安全"],
        filename="doc",
    )

    assert set(result.keys()) == {
        "filename",
        "requested_section_titles",
        "result_count",
        "results",
    }
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest -q tests/unit/test_handlers_dict.py`  
Expected: FAIL 或至少暴露旧 contract 不明确的地方。

- [ ] **Step 3: 写文档与补齐实现**

文档模板：

```markdown
## rag_search
Input:
- query: non-empty string
- top_k: int >= 1

Success:
{
  "query": "...",
  "mode": "...",
  "top_k": 5,
  "result_count": 2,
  "results": [...]
}

Error:
{
  "error": "INVALID_ARGUMENT",
  "message": "query 不能为空"
}
```

README 中补一个短节，指向 `docs/tool-contract.md`。

- [ ] **Step 4: 运行回归**

Run:

```bash
uv run pytest -q tests/unit/test_error_contract.py tests/unit/test_tool_output_contract.py tests/unit/test_transport_validation.py tests/unit/test_handlers_dict.py
```

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add README.md docs/tool-contract.md tests/unit/test_handlers_dict.py tests/unit/test_error_contract.py tests/unit/test_tool_output_contract.py tests/unit/test_transport_validation.py
git commit -m "docs: freeze tool contract and transport validation rules"
```

## 3) Phase 2 验收

- [ ] `ErrorCode` 成为统一业务错误码集合。
- [ ] handler 不再输出零散 error literal。
- [ ] 参数校验通过 `transport/validation.py` 收口。
- [ ] tool 成功返回结构被文档化且有测试覆盖。
- [ ] `uv run pytest -q tests/unit/test_error_contract.py tests/unit/test_tool_output_contract.py tests/unit/test_transport_validation.py tests/unit/test_handlers_dict.py` 全通过。

## 4) 签收记录

- [ ] Phase Owner: Pending
- [ ] QA/Reviewer: Pending
- [ ] Sign-off Date: Pending
- [ ] Sign-off Commit: Pending
- [ ] Notes: Pending

