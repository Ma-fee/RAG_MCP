# Stable Response Typing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 `phase4-runtime-merge` 中 `retrieval`、`resources`、`catalog` 的稳定成功返回结构补充 `TypedDict`，并同步收紧 service / handler 的成功返回注解，不改变实际对外字段。

**Architecture:** 保留现有 dataclass 作为内部构造表示，在模型模块中新增结果项 `TypedDict`，在 service 模块中新增成功响应体 `TypedDict`。`to_dict()`、service 成功返回、handler 成功返回注解统一改为明确类型，错误返回结构保持不动。

**Tech Stack:** Python 3.13, pytest, dataclasses, typing.TypedDict

---

## 0) Plan Review

- [ ] 已确认保留现有 dataclass，不改成纯 `TypedDict`。
- [ ] 已确认允许收紧 service / handler 成功返回注解。
- [ ] 已确认不修改错误返回结构。
- [ ] 已确认不改外部字段名和返回层级。
- [ ] Reviewer: Pending
- [ ] Review Date: 2026-04-07

## 1) 文件规划

**Modify**
- `src/rag_mcp/retrieval/models.py`
- `src/rag_mcp/retrieval/service.py`
- `src/rag_mcp/resources/models.py`
- `src/rag_mcp/resources/service.py`
- `src/rag_mcp/catalog/models.py`
- `src/rag_mcp/catalog/service.py`
- `src/rag_mcp/transport/handlers.py`
- `tests/unit/test_handlers_dict.py`
- `tests/unit/test_resource_service_multimodal.py`
- `tests/unit/test_hybrid_search.py`
- `tests/unit/test_rerank.py`

**Create**
- `tests/unit/test_response_typing.py`

## 2) 原子化 TDD Tasks

### Task 1: 收紧 retrieval 结果项和成功响应类型

**Files:**
- Modify: `src/rag_mcp/retrieval/models.py`
- Modify: `src/rag_mcp/retrieval/service.py`
- Modify: `src/rag_mcp/transport/handlers.py`
- Create: `tests/unit/test_response_typing.py`
- Modify/Test: `tests/unit/test_hybrid_search.py`
- Modify/Test: `tests/unit/test_rerank.py`

- [ ] **Step 1: 写失败测试**

```python
from typing import get_type_hints

from rag_mcp.retrieval.models import SearchHit, SearchHitDict
from rag_mcp.retrieval.service import RetrievalService, SearchResponseDict
from rag_mcp.transport.handlers import ToolHandlers


def test_search_hit_to_dict_returns_typed_dict_shape() -> None:
    payload = SearchHit(
        uri="rag://corpus/c1/d1#text-0",
        text="hello",
        title="Intro",
        score=0.9,
        metadata={"chunk_index": 0},
    ).to_dict()

    assert payload == {
        "uri": "rag://corpus/c1/d1#text-0",
        "text": "hello",
        "title": "Intro",
        "score": 0.9,
        "metadata": {"chunk_index": 0},
    }


def test_retrieval_search_annotations_use_response_typed_dict() -> None:
    service_hints = get_type_hints(RetrievalService.search)
    handler_hints = get_type_hints(ToolHandlers.search)

    assert service_hints["return"] == SearchResponseDict
    assert handler_hints["return"] == SearchResponseDict | dict[str, str]
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
uv run pytest -q tests/unit/test_response_typing.py::test_search_hit_to_dict_returns_typed_dict_shape tests/unit/test_response_typing.py::test_retrieval_search_annotations_use_response_typed_dict
```

Expected: FAIL，因为 `SearchHitDict` / `SearchResponseDict` 尚未定义，且返回注解仍是宽泛 dict。

- [ ] **Step 3: 写最小实现**

```python
class SearchHitDict(TypedDict):
    uri: str
    text: str
    title: str
    score: float
    metadata: dict[str, Any]
```

```python
@dataclass(frozen=True)
class SearchHit:
    ...

    def to_dict(self) -> SearchHitDict:
        return {...}
```

```python
class SearchResponseDict(TypedDict):
    query: str
    mode: str
    top_k: int
    result_count: int
    results: list[SearchHitDict]
```

```python
class RetrievalService:
    def search(...) -> SearchResponseDict:
        ...

    def _search_keyword(...) -> SearchResponseDict:
        ...

    def _search_rerank(...) -> SearchResponseDict:
        ...
```

```python
class ToolHandlers:
    def search(...) -> SearchResponseDict | dict[str, str]:
        ...
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
uv run pytest -q tests/unit/test_response_typing.py tests/unit/test_hybrid_search.py tests/unit/test_rerank.py
```

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add src/rag_mcp/retrieval/models.py src/rag_mcp/retrieval/service.py src/rag_mcp/transport/handlers.py tests/unit/test_response_typing.py tests/unit/test_hybrid_search.py tests/unit/test_rerank.py
git commit -m "refactor: type retrieval success responses"
```

### Task 2: 收紧 resources 成功返回类型

**Files:**
- Modify: `src/rag_mcp/resources/models.py`
- Modify: `src/rag_mcp/resources/service.py`
- Modify: `src/rag_mcp/transport/handlers.py`
- Modify/Test: `tests/unit/test_response_typing.py`
- Modify/Test: `tests/unit/test_resource_service_multimodal.py`

- [ ] **Step 1: 写失败测试**

```python
from typing import get_type_hints

from rag_mcp.resources.models import TextResourcePayload, TextResourcePayloadDict
from rag_mcp.resources.service import ReadResourceResponseDict, ResourceService
from rag_mcp.transport.handlers import ToolHandlers


def test_text_resource_payload_to_dict_returns_typed_dict_shape() -> None:
    payload = TextResourcePayload(
        uri="rag://corpus/c1/d1#text-0",
        text="hello",
        metadata={"chunk_index": 0},
    ).to_dict()

    assert payload == {
        "uri": "rag://corpus/c1/d1#text-0",
        "text": "hello",
        "metadata": {"chunk_index": 0},
    }


def test_resource_read_annotations_use_response_typed_dict() -> None:
    service_hints = get_type_hints(ResourceService.read)
    handler_hints = get_type_hints(ToolHandlers.read_resource)

    assert service_hints["return"] == ReadResourceResponseDict
    assert handler_hints["return"] == ReadResourceResponseDict | dict[str, str]
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
uv run pytest -q tests/unit/test_response_typing.py::test_text_resource_payload_to_dict_returns_typed_dict_shape tests/unit/test_response_typing.py::test_resource_read_annotations_use_response_typed_dict
```

Expected: FAIL，因为 `TextResourcePayloadDict` / `ReadResourceResponseDict` 尚未定义，且返回注解仍是宽泛 dict。

- [ ] **Step 3: 写最小实现**

```python
class TextResourcePayloadDict(TypedDict):
    uri: str
    text: str
    metadata: dict[str, Any]
```

```python
class ReadResourceResponseDict(TypedDict, total=False):
    uri: str
    text: str
    metadata: dict[str, Any]
    type: str
    doc_id: str
    element_id: str
    heading_path: str
    caption: str
    image_path: str
    page_number: int | None
    vlm_description: str
    markdown: str
    data_json: Any
    related: list[str]
```

```python
class ResourceService:
    def read(self, uri: str) -> ReadResourceResponseDict:
        ...
```

```python
class ToolHandlers:
    def read_resource(self, uri: str) -> ReadResourceResponseDict | dict[str, str]:
        ...
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
uv run pytest -q tests/unit/test_response_typing.py tests/unit/test_resource_service_multimodal.py
```

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add src/rag_mcp/resources/models.py src/rag_mcp/resources/service.py src/rag_mcp/transport/handlers.py tests/unit/test_response_typing.py tests/unit/test_resource_service_multimodal.py
git commit -m "refactor: type resource success responses"
```

### Task 3: 收紧 catalog 成功返回类型

**Files:**
- Modify: `src/rag_mcp/catalog/models.py`
- Modify: `src/rag_mcp/catalog/service.py`
- Modify: `src/rag_mcp/transport/handlers.py`
- Modify/Test: `tests/unit/test_response_typing.py`
- Modify/Test: `tests/unit/test_handlers_dict.py`

- [ ] **Step 1: 写失败测试**

```python
from typing import get_type_hints

from rag_mcp.catalog.models import SectionResult, SectionResultDict
from rag_mcp.catalog.service import (
    ListFilenamesResponseDict,
    ListSectionsResponseDict,
    SectionRetrievalResponseDict,
    CatalogQueryService,
)
from rag_mcp.transport.handlers import ToolHandlers


def test_section_result_to_dict_returns_typed_dict_shape() -> None:
    payload = SectionResult(
        uri="rag://corpus/c1/d1#text-0",
        title="1 Intro",
        text="hello",
        metadata={"chunk_index": 0},
        related_resource_uris=["rag://corpus/c1/d1#image-0"],
        related_resources=[{"uri": "rag://corpus/c1/d1#image-0", "type": "image"}],
    ).to_dict()

    assert payload["title"] == "1 Intro"
    assert payload["related_resource_uris"] == ["rag://corpus/c1/d1#image-0"]


def test_catalog_and_handler_annotations_use_typed_dicts() -> None:
    service_list_hints = get_type_hints(CatalogQueryService.list_filenames)
    service_sections_hints = get_type_hints(CatalogQueryService.list_sections)
    service_retrieval_hints = get_type_hints(CatalogQueryService.section_retrieval)
    handler_list_hints = get_type_hints(ToolHandlers.list_filenames)
    handler_sections_hints = get_type_hints(ToolHandlers.list_sections)
    handler_retrieval_hints = get_type_hints(ToolHandlers.section_retrieval)

    assert service_list_hints["return"] == ListFilenamesResponseDict
    assert service_sections_hints["return"] == ListSectionsResponseDict
    assert service_retrieval_hints["return"] == SectionRetrievalResponseDict
    assert handler_list_hints["return"] == ListFilenamesResponseDict | dict[str, str]
    assert handler_sections_hints["return"] == ListSectionsResponseDict | dict[str, str]
    assert handler_retrieval_hints["return"] == SectionRetrievalResponseDict | dict[str, str]
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
uv run pytest -q tests/unit/test_response_typing.py::test_section_result_to_dict_returns_typed_dict_shape tests/unit/test_response_typing.py::test_catalog_and_handler_annotations_use_typed_dicts
```

Expected: FAIL，因为 catalog 相关 `TypedDict` 及注解尚未定义。

- [ ] **Step 3: 写最小实现**

```python
class SectionResultDict(TypedDict):
    uri: str
    title: str
    text: str
    metadata: dict[str, Any]
    related_resource_uris: list[str]
    related_resources: list[dict[str, Any]]
```

```python
class FilenameItemDict(TypedDict):
    filename: str
    file_type: str
    chunk_count: int


class ListFilenamesResponseDict(TypedDict):
    count: int
    filenames: list[FilenameItemDict]
```

```python
class SectionItemDict(TypedDict):
    title: str
    heading_path: str
    section_title: str
    section_level: int
```

```python
class ListSectionsResponseDict(TypedDict):
    filename: str
    relative_path: str
    file_type: str
    section_count: int
    sections: list[SectionItemDict]


class SectionRetrievalResponseDict(TypedDict):
    query: str
    filename: str
    requested_titles: list[str]
    result_count: int
    results: list[SectionResultDict]
```

```python
class CatalogQueryService:
    def list_filenames(self) -> ListFilenamesResponseDict: ...
    def list_sections(self, filename: str) -> ListSectionsResponseDict: ...
    def section_retrieval(...) -> SectionRetrievalResponseDict: ...
```

```python
class ToolHandlers:
    def list_filenames(self) -> ListFilenamesResponseDict | dict[str, str]: ...
    def list_sections(self, filename: str) -> ListSectionsResponseDict | dict[str, str]: ...
    def section_retrieval(...) -> SectionRetrievalResponseDict | dict[str, str]: ...
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
uv run pytest -q tests/unit/test_response_typing.py tests/unit/test_handlers_dict.py
```

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add src/rag_mcp/catalog/models.py src/rag_mcp/catalog/service.py src/rag_mcp/transport/handlers.py tests/unit/test_response_typing.py tests/unit/test_handlers_dict.py
git commit -m "refactor: type catalog success responses"
```

### Task 4: 回归验证稳定成功返回类型收口

**Files:**
- Modify: `src/rag_mcp/retrieval/models.py`
- Modify: `src/rag_mcp/retrieval/service.py`
- Modify: `src/rag_mcp/resources/models.py`
- Modify: `src/rag_mcp/resources/service.py`
- Modify: `src/rag_mcp/catalog/models.py`
- Modify: `src/rag_mcp/catalog/service.py`
- Modify: `src/rag_mcp/transport/handlers.py`
- Test: `tests/unit/test_response_typing.py`
- Test: `tests/unit/test_handlers_dict.py`
- Test: `tests/unit/test_resource_service_multimodal.py`
- Test: `tests/unit/test_hybrid_search.py`
- Test: `tests/unit/test_rerank.py`

- [ ] **Step 1: 运行聚焦测试**

Run:

```bash
uv run pytest -q tests/unit/test_response_typing.py tests/unit/test_handlers_dict.py tests/unit/test_resource_service_multimodal.py tests/unit/test_hybrid_search.py tests/unit/test_rerank.py
```

Expected: PASS。

- [ ] **Step 2: 运行关键集成测试**

Run:

```bash
uv run pytest -q tests/integration/test_phase3_structure_and_uri_stability.py tests/integration/test_e2e_multimodal.py
```

Expected: PASS。

- [ ] **Step 3: 检查目标成功返回注解已收紧**

Run:

```bash
rg -n "-> dict\\[str, Any\\]|-> dict$|to_dict\\(self\\) -> dict\\[str, Any\\]" src/rag_mcp/retrieval/models.py src/rag_mcp/retrieval/service.py src/rag_mcp/resources/models.py src/rag_mcp/resources/service.py src/rag_mcp/catalog/models.py src/rag_mcp/catalog/service.py src/rag_mcp/transport/handlers.py
```

Expected: 无输出，或仅剩本轮明确不处理的错误返回辅助函数。

- [ ] **Step 4: 提交**

```bash
git add src/rag_mcp/retrieval/models.py src/rag_mcp/retrieval/service.py src/rag_mcp/resources/models.py src/rag_mcp/resources/service.py src/rag_mcp/catalog/models.py src/rag_mcp/catalog/service.py src/rag_mcp/transport/handlers.py tests/unit/test_response_typing.py tests/unit/test_handlers_dict.py tests/unit/test_resource_service_multimodal.py tests/unit/test_hybrid_search.py tests/unit/test_rerank.py
git commit -m "refactor: type stable success response payloads"
```
