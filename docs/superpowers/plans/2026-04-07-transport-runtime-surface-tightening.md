# Transport Runtime Surface Tightening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 收紧 `phase4-runtime-merge` 中 transport/runtime 最外层入口与残余外围 helper 的宽泛类型，让现有成功返回与依赖类型真正贯通到 surface。

**Architecture:** 复用已经建立好的 success response `TypedDict` 和 runtime `Protocol`，让 `mcp_server`、`fastapi_app`、`reranker factory`、`rebuild` 外层函数和 sections mapping repository 不再退化成 `dict` / `Any`。行为和字段保持不变，只收紧类型表达。

**Tech Stack:** Python 3.13, pytest, typing.Protocol, typing.TypedDict, FastMCP, FastAPI

---

## 0) Plan Review

- [ ] 已确认本轮不修改外部行为和 JSON 字段。
- [ ] 已确认本轮不修改错误返回结构。
- [ ] 已确认本轮只收 transport/runtime surface 与残余外围 helper。
- [ ] 已确认允许新增最小只读 service `Protocol`。
- [ ] Reviewer: Pending
- [ ] Review Date: 2026-04-07

## 1) 文件规划

**Modify**
- `src/rag_mcp/transport/mcp_server.py`
- `src/rag_mcp/transport/fastapi_app.py`
- `src/rag_mcp/retrieval/reranker.py`
- `src/rag_mcp/indexing/rebuild.py`
- `src/rag_mcp/indexing/services.py`
- `src/rag_mcp/indexing/repositories.py`
- `src/rag_mcp/runtime_types.py`
- `tests/unit/test_mcp_server.py`
- `tests/unit/test_fastapi_app.py`
- `tests/unit/test_rerank.py`
- `tests/unit/test_resource_store.py`
- `tests/unit/test_keyword_index.py`

## 2) 原子化 TDD Tasks

### Task 1: 收紧 MCP server surface 返回注解

**Files:**
- Modify: `src/rag_mcp/transport/mcp_server.py`
- Modify/Test: `tests/unit/test_mcp_server.py`

- [ ] **Step 1: 写失败测试**

```python
from typing import get_type_hints

from rag_mcp.transport.mcp_server import create_mcp_server


def test_mcp_server_tool_annotations_use_typed_handler_outputs() -> None:
    hints = get_type_hints(create_mcp_server)
    assert hints["return"]
```

```python
def test_mcp_tool_functions_do_not_annotate_plain_dict() -> None:
    import rag_mcp.transport.mcp_server as mcp_server

    source = Path(mcp_server.__file__).read_text(encoding="utf-8")

    assert "def rag_search(query: str, top_k: int = 5) -> dict:" not in source
    assert "def rag_read_resource(uri: str) -> dict:" not in source
    assert "def rag_list_filenames() -> dict:" not in source
    assert "def rag_list_sections(filename: str) -> dict:" not in source
    assert "def rag_section_retrieval(" in source
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
uv run pytest -q tests/unit/test_mcp_server.py::test_mcp_tool_functions_do_not_annotate_plain_dict
```

Expected: FAIL，因为 `mcp_server.py` 中 tool/resource 仍标注为裸 `dict`。

- [ ] **Step 3: 写最小实现**

将 `mcp_server.py` 中：

- `rag_search`
- `rag_read_resource`
- `rag_list_filenames`
- `rag_list_sections`
- `rag_section_retrieval`
- `rag_resource`

的返回注解改为与 `ToolHandlers` 对应方法一致的成功返回联合类型。

对 `rag_rebuild_index` / `rag_index_status`，若本轮 Task 4 中补出明确 success type，则同步替换；否则先保持最小但不使用裸 `dict`。

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
uv run pytest -q tests/unit/test_mcp_server.py
```

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add src/rag_mcp/transport/mcp_server.py tests/unit/test_mcp_server.py
git commit -m "refactor: tighten mcp server surface annotations"
```

### Task 2: 收紧 FastAPI app 依赖类型

**Files:**
- Modify: `src/rag_mcp/transport/fastapi_app.py`
- Modify: `src/rag_mcp/runtime_types.py`
- Modify/Test: `tests/unit/test_fastapi_app.py`

- [ ] **Step 1: 写失败测试**

```python
from typing import get_type_hints

from rag_mcp.transport.fastapi_app import create_app
from rag_mcp.runtime_types import ReadableResourceService


def test_fastapi_app_uses_readable_resource_service_protocol() -> None:
    hints = get_type_hints(create_app)
    assert hints["resource_service"] == ReadableResourceService
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
uv run pytest -q tests/unit/test_fastapi_app.py::test_fastapi_app_uses_readable_resource_service_protocol
```

Expected: FAIL，因为 `resource_service` 当前仍是 `Any`。

- [ ] **Step 3: 写最小实现**

在 `runtime_types.py` 中新增：

```python
class ReadableResourceService(Protocol):
    def read(self, uri: str) -> ReadResourceResponseDict: ...
```

若需要避免循环引用，可使用 `TYPE_CHECKING` 或延迟注解。

并将：

```python
def create_app(resource_service: ReadableResourceService, data_dir: Path) -> FastAPI:
```

替换当前 `Any`。

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
uv run pytest -q tests/unit/test_fastapi_app.py
```

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add src/rag_mcp/runtime_types.py src/rag_mcp/transport/fastapi_app.py tests/unit/test_fastapi_app.py
git commit -m "refactor: type fastapi resource service dependency"
```

### Task 3: 收紧 reranker factory 返回类型

**Files:**
- Modify: `src/rag_mcp/retrieval/reranker.py`
- Modify/Test: `tests/unit/test_rerank.py`

- [ ] **Step 1: 写失败测试**

```python
from typing import get_type_hints

from rag_mcp.retrieval.reranker import build_reranker
from rag_mcp.runtime_types import RerankerLike


def test_build_reranker_annotation_uses_reranker_protocol() -> None:
    hints = get_type_hints(build_reranker)
    assert hints["return"] == RerankerLike | None
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
uv run pytest -q tests/unit/test_rerank.py::test_build_reranker_annotation_uses_reranker_protocol
```

Expected: FAIL，因为当前返回仍是 `Any | None`。

- [ ] **Step 3: 写最小实现**

将：

```python
def build_reranker(cfg: "AppConfig") -> RerankerLike | None:
```

并收紧 `ApiReranker.rerank()` 的候选与返回类型，使其与 `RerankerLike` 一致。

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
uv run pytest -q tests/unit/test_rerank.py
```

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add src/rag_mcp/retrieval/reranker.py tests/unit/test_rerank.py
git commit -m "refactor: type reranker factory surface"
```

### Task 4: 收紧 rebuild 和 sections mapping 外围返回

**Files:**
- Modify: `src/rag_mcp/indexing/services.py`
- Modify: `src/rag_mcp/indexing/rebuild.py`
- Modify: `src/rag_mcp/indexing/repositories.py`
- Modify/Test: `tests/unit/test_resource_store.py`
- Modify/Test: `tests/unit/test_keyword_index.py`

- [ ] **Step 1: 写失败测试**

```python
from typing import get_type_hints

from rag_mcp.indexing.rebuild import rebuild_keyword_index
from rag_mcp.indexing.repositories import SectionsMappingRepository
from rag_mcp.indexing.services import RebuildIndexService, RebuildIndexResponseDict


def test_rebuild_annotations_use_response_dict() -> None:
    rebuild_hints = get_type_hints(rebuild_keyword_index)
    service_hints = get_type_hints(RebuildIndexService.rebuild_keyword_index)

    assert rebuild_hints["return"] == RebuildIndexResponseDict
    assert service_hints["return"] == RebuildIndexResponseDict


def test_sections_mapping_repository_annotation_is_specific() -> None:
    hints = get_type_hints(SectionsMappingRepository.load)
    assert hints["return"] == dict[str, list[str]]
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
uv run pytest -q tests/unit/test_resource_store.py::test_rebuild_annotations_use_response_dict tests/unit/test_keyword_index.py::test_sections_mapping_repository_annotation_is_specific
```

Expected: FAIL，因为返回类型仍是宽泛 dict。

- [ ] **Step 3: 写最小实现**

在 `services.py` 中新增：

```python
class RebuildIndexResponseDict(TypedDict):
    corpus_id: str
    index_dir: str
    indexed_at: int
    document_count: int
    chunk_count: int
    embedding_model: str | None
    embedding_dimension: int | None
```

并收紧：

- `RebuildIndexService.rebuild_keyword_index() -> RebuildIndexResponseDict`
- `indexing.rebuild.rebuild_keyword_index() -> RebuildIndexResponseDict`
- `SectionsMappingRepository.load() -> dict[str, list[str]]`

如果需要，`ToolHandlers.rebuild_index()` 可继续返回更窄的 handler-facing dict，但中间 `result` 类型应来自 `RebuildIndexResponseDict`。

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
uv run pytest -q tests/unit/test_resource_store.py tests/unit/test_keyword_index.py
```

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add src/rag_mcp/indexing/services.py src/rag_mcp/indexing/rebuild.py src/rag_mcp/indexing/repositories.py tests/unit/test_resource_store.py tests/unit/test_keyword_index.py
git commit -m "refactor: type rebuild and sections mapping surfaces"
```

### Task 5: 回归验证 transport/runtime surface 收口

**Files:**
- Modify: `src/rag_mcp/transport/mcp_server.py`
- Modify: `src/rag_mcp/transport/fastapi_app.py`
- Modify: `src/rag_mcp/retrieval/reranker.py`
- Modify: `src/rag_mcp/indexing/rebuild.py`
- Modify: `src/rag_mcp/indexing/services.py`
- Modify: `src/rag_mcp/indexing/repositories.py`
- Modify: `src/rag_mcp/runtime_types.py`
- Test: `tests/unit/test_mcp_server.py`
- Test: `tests/unit/test_fastapi_app.py`
- Test: `tests/unit/test_rerank.py`
- Test: `tests/unit/test_resource_store.py`
- Test: `tests/unit/test_keyword_index.py`

- [ ] **Step 1: 运行聚焦测试**

Run:

```bash
uv run pytest -q tests/unit/test_mcp_server.py tests/unit/test_fastapi_app.py tests/unit/test_rerank.py tests/unit/test_resource_store.py tests/unit/test_keyword_index.py
```

Expected: PASS。

- [ ] **Step 2: 运行关键集成测试**

Run:

```bash
uv run pytest -q tests/integration/test_phase3_structure_and_uri_stability.py tests/integration/test_e2e_multimodal.py
```

Expected: PASS。

- [ ] **Step 3: 扫描目标模块中的残余 surface 宽泛类型**

Run:

```bash
rg -n -e "-> dict$" -e "-> dict\\[str, Any\\]" -e "Any \\| None" src/rag_mcp/transport/mcp_server.py src/rag_mcp/transport/fastapi_app.py src/rag_mcp/retrieval/reranker.py src/rag_mcp/indexing/rebuild.py src/rag_mcp/indexing/services.py src/rag_mcp/indexing/repositories.py
```

Expected: 只剩本轮明确不处理的内部 helper，不应再出现在最外层 surface、factory 返回或 sections mapping 返回上。

- [ ] **Step 4: 提交**

```bash
git add src/rag_mcp/transport/mcp_server.py src/rag_mcp/transport/fastapi_app.py src/rag_mcp/retrieval/reranker.py src/rag_mcp/indexing/rebuild.py src/rag_mcp/indexing/services.py src/rag_mcp/indexing/repositories.py src/rag_mcp/runtime_types.py tests/unit/test_mcp_server.py tests/unit/test_fastapi_app.py tests/unit/test_rerank.py tests/unit/test_resource_store.py tests/unit/test_keyword_index.py
git commit -m "refactor: tighten transport and runtime surface types"
```
