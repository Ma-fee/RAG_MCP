# Indexing Schema Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 `phase4-runtime-merge` 的 indexing 路径建立共享 schema `TypedDict`，并收紧 repository / manifest / persistence / service / index adapter 的关键数据类型边界，不改变现有 JSON 字段。

**Architecture:** 新增 `src/rag_mcp/indexing/types.py` 作为单一 schema 模块，先收 manifest / repository payload，再收 keyword / resource entry，最后收 vector entry / hit。现有持久化格式保持不变，只调整类型表达和相关测试。

**Tech Stack:** Python 3.13, pytest, typing.TypedDict, dataclasses, json

---

## 0) Plan Review

- [ ] 已确认本轮只收 indexing schema layer，不碰外部 MCP tool contract。
- [ ] 已确认不重构 docling / parser 的第三方对象边界。
- [ ] 已确认 JSON 文件字段保持不变。
- [ ] 已确认允许新增 `src/rag_mcp/indexing/types.py`。
- [ ] Reviewer: Pending
- [ ] Review Date: 2026-04-07

## 1) 文件规划

**Create**
- `src/rag_mcp/indexing/types.py`
- `tests/unit/test_indexing_types.py`
- `tests/unit/test_repositories.py`

**Modify**
- `src/rag_mcp/indexing/repositories.py`
- `src/rag_mcp/indexing/manifest.py`
- `src/rag_mcp/indexing/persistence.py`
- `src/rag_mcp/indexing/resource_store.py`
- `src/rag_mcp/indexing/services.py`
- `src/rag_mcp/indexing/rebuild.py`
- `src/rag_mcp/indexing/keyword_index.py`
- `src/rag_mcp/indexing/vector_index.py`
- `tests/unit/test_resource_store.py`
- `tests/unit/test_keyword_index.py`
- `tests/unit/test_vector_index.py`

## 2) 原子化 TDD Tasks

### Task 1: 建立共享 indexing schema 与 manifest / repository 类型

**Files:**
- Create: `src/rag_mcp/indexing/types.py`
- Create: `tests/unit/test_indexing_types.py`
- Create: `tests/unit/test_repositories.py`
- Modify: `src/rag_mcp/indexing/repositories.py`
- Modify: `src/rag_mcp/indexing/manifest.py`

- [ ] **Step 1: 写失败测试**

```python
from typing import get_type_hints

from rag_mcp.indexing.manifest import read_active_manifest
from rag_mcp.indexing.repositories import (
    ActiveIndexRepository,
    KeywordStoreRepository,
    ResourceStoreRepository,
)
from rag_mcp.indexing.types import (
    ActiveManifestDict,
    KeywordEntryDict,
    KeywordStorePayloadDict,
    ResourceEntryDict,
    ResourceStorePayloadDict,
)


def test_manifest_and_repository_annotations_use_shared_schema_types() -> None:
    manifest_hints = get_type_hints(read_active_manifest)
    active_repo_hints = get_type_hints(ActiveIndexRepository.load)
    keyword_repo_hints = get_type_hints(KeywordStoreRepository.load)
    resource_repo_hints = get_type_hints(ResourceStoreRepository.load)

    assert manifest_hints["return"] == ActiveManifestDict | None
    assert active_repo_hints["return"] == ActiveManifestDict
    assert keyword_repo_hints["return"] == KeywordStorePayloadDict
    assert resource_repo_hints["return"] == ResourceStorePayloadDict
```

```python
def test_keyword_store_repository_entries_return_typed_entries(tmp_path: Path) -> None:
    index_dir = tmp_path / "idx"
    index_dir.mkdir()
    (index_dir / "keyword_store.json").write_text(
        json.dumps(
            {
                "corpus_id": "c1",
                "entries": [
                    {
                        "uri": "rag://corpus/c1/d1#text-0",
                        "text": "hello",
                        "title": "Intro",
                        "metadata": {"chunk_index": 0, "doc_id": "d1", "corpus_id": "c1"},
                        "related_resource_uris": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    entries = KeywordStoreRepository(index_dir=index_dir).entries()

    assert entries[0]["uri"] == "rag://corpus/c1/d1#text-0"
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
uv run pytest -q tests/unit/test_indexing_types.py tests/unit/test_repositories.py
```

Expected: FAIL，因为 `indexing.types` 和共享 schema 类型尚未定义。

- [ ] **Step 3: 写最小实现**

```python
class ActiveManifestDict(TypedDict):
    corpus_id: str
    index_dir: str
    indexed_at: int
    document_count: int
    chunk_count: int
    embedding_model: str | None
    embedding_dimension: int | None
```

```python
class KeywordEntryMetadataDict(TypedDict, total=False):
    corpus_id: str
    doc_id: str
    chunk_index: int
    file_type: str
    section_title: str
    heading_path: str
    section_level: int
    relative_path: str
    chunk_length: int
```

```python
class KeywordEntryDict(TypedDict, total=False):
    text: str
    title: str
    uri: str
    metadata: KeywordEntryMetadataDict
    related_resource_uris: list[str]
    resource_metadata: dict[str, list[str]]
    score: float
```

```python
class KeywordStorePayloadDict(TypedDict, total=False):
    corpus_id: str
    avgdl: float
    idf: dict[str, float]
    entries: list[KeywordEntryDict]
```

```python
class ResourceEntryDict(TypedDict, total=False):
    uri: str
    type: str
    doc_id: str
    element_id: str
    text: str
    heading_path: str
    section_title: str
    section_level: int
    caption: str
    image_path: str
    page_number: int | None
    vlm_description: str
    markdown: str
    data_json: object
    related: list[str]
```

```python
class ResourceStorePayloadDict(TypedDict):
    entries: list[ResourceEntryDict]
```

并将：

- `read_active_manifest() -> ActiveManifestDict | None`
- `ActiveIndexRepository.load() -> ActiveManifestDict`
- `KeywordStoreRepository.load() -> KeywordStorePayloadDict`
- `KeywordStoreRepository.entries() -> list[KeywordEntryDict]`
- `ResourceStoreRepository.load() -> ResourceStorePayloadDict`
- `ResourceStoreRepository.entries() -> list[ResourceEntryDict]`
- `ResourceStoreRepository.get() -> ResourceEntryDict | None`

全部接到共享类型。

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
uv run pytest -q tests/unit/test_indexing_types.py tests/unit/test_repositories.py
```

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add src/rag_mcp/indexing/types.py src/rag_mcp/indexing/repositories.py src/rag_mcp/indexing/manifest.py tests/unit/test_indexing_types.py tests/unit/test_repositories.py
git commit -m "refactor: add indexing schema types for repository payloads"
```

### Task 2: 收紧 resource / keyword entry 构建与持久化边界

**Files:**
- Modify: `src/rag_mcp/indexing/resource_store.py`
- Modify: `src/rag_mcp/indexing/services.py`
- Modify: `src/rag_mcp/indexing/persistence.py`
- Modify: `src/rag_mcp/indexing/rebuild.py`
- Modify/Test: `tests/unit/test_resource_store.py`
- Modify/Test: `tests/unit/test_keyword_index.py`

- [ ] **Step 1: 写失败测试**

```python
from typing import get_type_hints

from rag_mcp.indexing.resource_store import ResourceStore
from rag_mcp.indexing.services import RebuildIndexService
from rag_mcp.indexing.persistence import IndexPersistenceService
from rag_mcp.indexing.types import KeywordEntryDict, ResourceEntryDict


def test_resource_and_keyword_build_paths_use_shared_entry_types() -> None:
    resource_store_hints = get_type_hints(ResourceStore.build)
    persistence_resource_hints = get_type_hints(IndexPersistenceService.write_resource_store)
    persistence_keyword_hints = get_type_hints(IndexPersistenceService.write_keyword_store)

    assert resource_store_hints["return"] == list[ResourceEntryDict]
    assert persistence_resource_hints["entries"] == list[ResourceEntryDict]
    assert persistence_keyword_hints["entries"] == list[KeywordEntryDict]
```

```python
def test_resource_store_get_annotation_returns_resource_entry_dict() -> None:
    hints = get_type_hints(ResourceStore.get)
    assert str(hints["return"]).endswith("ResourceEntryDict | None")
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
uv run pytest -q tests/unit/test_resource_store.py::test_resource_and_keyword_build_paths_use_shared_entry_types tests/unit/test_resource_store.py::test_resource_store_get_annotation_returns_resource_entry_dict
```

Expected: FAIL，因为相关注解仍是裸 dict / `dict[str, Any]`。

- [ ] **Step 3: 写最小实现**

将以下边界接入共享类型：

- `ResourceStore.build() -> list[ResourceEntryDict]`
- `ResourceStore.get() -> ResourceEntryDict | None`
- `ResourceStore._text_entry() -> ResourceEntryDict`
- `ResourceStore._image_entry() -> ResourceEntryDict`
- `ResourceStore._table_entry() -> ResourceEntryDict`
- `IndexPersistenceService.write_resource_store(entries: list[ResourceEntryDict])`
- `IndexPersistenceService.write_keyword_store(entries: list[KeywordEntryDict])`
- `RebuildIndexService` 中 `entries` / `all_resource_entries` / `_build_doc_element_resource_uri_map()` / `_entry_id()` 的关键 entry 类型
- `rebuild._build_and_persist_keyword_store()` 的入参与返回类型保持和 service 一致

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
uv run pytest -q tests/unit/test_resource_store.py tests/unit/test_keyword_index.py
```

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add src/rag_mcp/indexing/resource_store.py src/rag_mcp/indexing/services.py src/rag_mcp/indexing/persistence.py src/rag_mcp/indexing/rebuild.py tests/unit/test_resource_store.py tests/unit/test_keyword_index.py
git commit -m "refactor: type indexing entry build and persistence paths"
```

### Task 3: 收紧 keyword / vector index adapter 边界

**Files:**
- Modify: `src/rag_mcp/indexing/keyword_index.py`
- Modify: `src/rag_mcp/indexing/vector_index.py`
- Modify: `src/rag_mcp/indexing/types.py`
- Modify/Test: `tests/unit/test_keyword_index.py`
- Modify/Test: `tests/unit/test_vector_index.py`

- [ ] **Step 1: 写失败测试**

```python
from typing import get_type_hints

from rag_mcp.indexing.keyword_index import KeywordIndex, persist_keyword_store
from rag_mcp.indexing.vector_index import VectorIndex
from rag_mcp.indexing.types import (
    KeywordEntryDict,
    KeywordStorePayloadDict,
    VectorChunkEntryDict,
    VectorSearchHitDict,
)


def test_index_adapters_use_shared_schema_types() -> None:
    keyword_init_hints = get_type_hints(KeywordIndex.__init__)
    keyword_search_hints = get_type_hints(KeywordIndex.search)
    persist_hints = get_type_hints(persist_keyword_store)
    vector_upsert_hints = get_type_hints(VectorIndex.upsert_chunks)
    vector_search_hints = get_type_hints(VectorIndex.search_by_vector)

    assert keyword_init_hints["entries"] == list[KeywordEntryDict]
    assert keyword_search_hints["return"] == list[KeywordEntryDict]
    assert persist_hints["entries"] == list[KeywordEntryDict]
    assert vector_upsert_hints["entries"] == list[VectorChunkEntryDict]
    assert vector_search_hints["return"] == list[VectorSearchHitDict]
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
uv run pytest -q tests/unit/test_vector_index.py::test_index_adapters_use_shared_schema_types
```

Expected: FAIL，因为 vector / keyword adapter 仍使用宽泛 dict。

- [ ] **Step 3: 写最小实现**

在 `src/rag_mcp/indexing/types.py` 中补充：

```python
class VectorChunkEntryDict(TypedDict):
    id: str
    text: str
    uri: str
    title: str
    metadata: KeywordEntryMetadataDict


class VectorSearchHitDict(VectorChunkEntryDict, total=False):
    score: float
```

并收紧：

- `KeywordIndex.__init__(entries: list[KeywordEntryDict], ...)`
- `KeywordIndex.search(...) -> list[KeywordEntryDict]`
- `persist_keyword_store(..., entries: list[KeywordEntryDict])`
- `VectorIndex.upsert_chunks(entries: list[VectorChunkEntryDict], ...)`
- `VectorIndex.search_by_vector(...) -> list[VectorSearchHitDict]`

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
uv run pytest -q tests/unit/test_keyword_index.py tests/unit/test_vector_index.py
```

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add src/rag_mcp/indexing/types.py src/rag_mcp/indexing/keyword_index.py src/rag_mcp/indexing/vector_index.py tests/unit/test_keyword_index.py tests/unit/test_vector_index.py
git commit -m "refactor: type indexing adapters with shared schema"
```

### Task 4: 回归验证 indexing schema layer 收口

**Files:**
- Modify: `src/rag_mcp/indexing/types.py`
- Modify: `src/rag_mcp/indexing/repositories.py`
- Modify: `src/rag_mcp/indexing/manifest.py`
- Modify: `src/rag_mcp/indexing/persistence.py`
- Modify: `src/rag_mcp/indexing/resource_store.py`
- Modify: `src/rag_mcp/indexing/services.py`
- Modify: `src/rag_mcp/indexing/rebuild.py`
- Modify: `src/rag_mcp/indexing/keyword_index.py`
- Modify: `src/rag_mcp/indexing/vector_index.py`
- Test: `tests/unit/test_indexing_types.py`
- Test: `tests/unit/test_repositories.py`
- Test: `tests/unit/test_resource_store.py`
- Test: `tests/unit/test_keyword_index.py`
- Test: `tests/unit/test_vector_index.py`

- [ ] **Step 1: 运行聚焦测试**

Run:

```bash
uv run pytest -q tests/unit/test_indexing_types.py tests/unit/test_repositories.py tests/unit/test_resource_store.py tests/unit/test_keyword_index.py tests/unit/test_vector_index.py
```

Expected: PASS。

- [ ] **Step 2: 运行关键回归测试**

Run:

```bash
uv run pytest -q tests/integration/test_phase3_structure_and_uri_stability.py tests/integration/test_e2e_multimodal.py
```

Expected: PASS。

- [ ] **Step 3: 扫描关键 indexing 模块中的宽泛 entry 类型**

Run:

```bash
rg -n -e "list\\[Any\\]" -e "dict\\[str, Any\\]" src/rag_mcp/indexing/repositories.py src/rag_mcp/indexing/manifest.py src/rag_mcp/indexing/persistence.py src/rag_mcp/indexing/resource_store.py src/rag_mcp/indexing/services.py src/rag_mcp/indexing/rebuild.py src/rag_mcp/indexing/keyword_index.py src/rag_mcp/indexing/vector_index.py
```

Expected: 只剩本轮明确不处理的开放字段或第三方边界，不应再出现在 repository / manifest / entry adapter 主路径返回和入参上。

- [ ] **Step 4: 提交**

```bash
git add src/rag_mcp/indexing/types.py src/rag_mcp/indexing/repositories.py src/rag_mcp/indexing/manifest.py src/rag_mcp/indexing/persistence.py src/rag_mcp/indexing/resource_store.py src/rag_mcp/indexing/services.py src/rag_mcp/indexing/rebuild.py src/rag_mcp/indexing/keyword_index.py src/rag_mcp/indexing/vector_index.py tests/unit/test_indexing_types.py tests/unit/test_repositories.py tests/unit/test_resource_store.py tests/unit/test_keyword_index.py tests/unit/test_vector_index.py
git commit -m "refactor: add shared indexing schema types"
```
