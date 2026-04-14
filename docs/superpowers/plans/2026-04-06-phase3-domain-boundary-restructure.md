# Phase 3 Domain Boundary Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Phase 2 稳定 contract 之后，进一步整理 `indexing`、`catalog`、`resources`、`retrieval` 的领域边界，建立 query/write 清晰分层，并引入内部 payload model。

**Architecture:** `indexing` 负责 write-side orchestration 与 persistence；`catalog` / `resources` / `retrieval` 负责 query-side；repository 只做数据访问；service 只做业务逻辑；内部 payload 通过 dataclass 或轻量 Pydantic model 约束，但 transport 仍输出 dict。

**Tech Stack:** Python 3.13, pytest, dataclasses, optional pydantic, pathlib

---

## 0) Plan Review

- [ ] 已确认本 Phase 不修改 Phase 2 固定的 tool contract。
- [ ] 已确认本 Phase 不重写 transport 类型。
- [ ] 已确认本 Phase 可以引入内部 model，但 MCP 输出仍保持 dict。
- [ ] 已确认 write-side / read-side 分离优先于目录物理迁移。
- [ ] Reviewer: Pending
- [ ] Review Date: 2026-04-06

## 1) 文件规划

**Create**
- `src/rag_mcp/indexing/persistence.py`
- `src/rag_mcp/indexing/services.py`
- `src/rag_mcp/catalog/models.py`
- `src/rag_mcp/retrieval/models.py`
- `src/rag_mcp/resources/models.py`
- `tests/unit/test_indexing_services.py`
- `tests/unit/test_internal_models.py`
- `tests/unit/test_architecture_boundaries.py`
- `docs/architecture/query-write-boundary.md`

**Modify**
- `src/rag_mcp/indexing/rebuild.py`
- `src/rag_mcp/catalog/service.py`
- `src/rag_mcp/resources/service.py`
- `src/rag_mcp/retrieval/service.py`
- `src/rag_mcp/indexing/repositories.py`
- `tests/unit/test_rebuild_multimodal.py`
- `tests/unit/test_catalog_service.py`
- `tests/unit/test_resource_service_multimodal.py`
- `tests/unit/test_hybrid_search.py`

## 2) 原子化 TDD Tasks

### Task 1: 拆分 indexing 写路径 orchestration / persistence

**Files:**
- Create: `src/rag_mcp/indexing/persistence.py`
- Create: `src/rag_mcp/indexing/services.py`
- Modify: `src/rag_mcp/indexing/rebuild.py`
- Test: `tests/unit/test_indexing_services.py`
- Modify/Test: `tests/unit/test_rebuild_multimodal.py`

- [ ] **Step 1: 写失败测试**

```python
def test_index_persistence_service_writes_all_stores(tmp_path: Path) -> None:
    svc = IndexPersistenceService(index_dir=tmp_path / "idx", data_dir=tmp_path)

    svc.write_keyword_store({"entries": []})
    svc.write_resource_store({"entries": []})
    svc.write_sections_mapping({"doc": ["1 前言"]})

    assert (tmp_path / "idx" / "keyword_store.json").exists()
    assert (tmp_path / "idx" / "resource_store.json").exists()
    assert (tmp_path / "idx" / "sections_mapping.json").exists()
```

再补：
- `RebuildIndexService` 最终调用 persistence
- `rebuild.py` 的公开入口仍返回旧 manifest payload 结构

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
uv run pytest -q tests/unit/test_indexing_services.py
uv run pytest -q tests/unit/test_rebuild_multimodal.py
```

Expected: FAIL。

- [ ] **Step 3: 写最小实现**

```python
class IndexPersistenceService:
    def __init__(self, index_dir: Path, data_dir: Path) -> None:
        self.index_dir = index_dir
        self.data_dir = data_dir

    def write_keyword_store(self, payload: dict[str, Any]) -> None: ...
    def write_resource_store(self, payload: dict[str, Any]) -> None: ...
    def write_sections_mapping(self, payload: dict[str, list[str]]) -> None: ...
    def write_manifest(self, payload: dict[str, Any]) -> None: ...
```

```python
class RebuildIndexService:
    def rebuild(self, source_dir: Path, *, data_dir: Path, embedding_provider: Any | None = None, vlm_client: Any | None = None) -> dict[str, Any]:
        ...
```

然后让 `rebuild_keyword_index(...)` 只做薄封装并调用 `RebuildIndexService`。

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
uv run pytest -q tests/unit/test_indexing_services.py
uv run pytest -q tests/unit/test_rebuild_multimodal.py
```

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add src/rag_mcp/indexing/persistence.py src/rag_mcp/indexing/services.py src/rag_mcp/indexing/rebuild.py tests/unit/test_indexing_services.py tests/unit/test_rebuild_multimodal.py
git commit -m "refactor: split indexing orchestration and persistence"
```

### Task 2: 固定 query-side service 边界

**Files:**
- Modify: `src/rag_mcp/catalog/service.py`
- Modify: `src/rag_mcp/resources/service.py`
- Modify: `src/rag_mcp/retrieval/service.py`
- Test: `tests/unit/test_architecture_boundaries.py`

- [ ] **Step 1: 写失败测试**

```python
def test_catalog_service_does_not_return_transport_error_dict() -> None:
    source = Path("src/rag_mcp/catalog/service.py").read_text(encoding="utf-8")
    assert '"error"' not in source or "ServiceException" in source
```

```python
def test_retrieval_service_does_not_import_transport_modules() -> None:
    source = Path("src/rag_mcp/retrieval/service.py").read_text(encoding="utf-8")
    assert "rag_mcp.transport" not in source
```

这类测试不追求完美 AST 校验，但要能阻止明显越界。

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest -q tests/unit/test_architecture_boundaries.py`  
Expected: FAIL 或暴露现有边界违规点。

- [ ] **Step 3: 写最小实现**

收口目标：

```text
CatalogQueryService -> 目录浏览 / section retrieval
ResourceService -> rag:// 资源读取
RetrievalService -> keyword/vector/hybrid 查询编排
ToolHandlers -> 参数适配 + 异常翻译
```

必要时删除 service 中遗留的 transport 风格输出代码，统一改为 `return payload` 或 `raise ServiceException(...)`。

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
uv run pytest -q tests/unit/test_architecture_boundaries.py
uv run pytest -q tests/unit/test_catalog_service.py tests/unit/test_resource_service_multimodal.py tests/unit/test_hybrid_search.py
```

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add src/rag_mcp/catalog/service.py src/rag_mcp/resources/service.py src/rag_mcp/retrieval/service.py tests/unit/test_architecture_boundaries.py tests/unit/test_catalog_service.py tests/unit/test_resource_service_multimodal.py tests/unit/test_hybrid_search.py
git commit -m "refactor: stabilize query service boundaries"
```

### Task 3: 引入内部 payload model

**Files:**
- Create: `src/rag_mcp/catalog/models.py`
- Create: `src/rag_mcp/retrieval/models.py`
- Create: `src/rag_mcp/resources/models.py`
- Modify: corresponding services
- Test: `tests/unit/test_internal_models.py`

- [ ] **Step 1: 写失败测试**

```python
def test_search_hit_model_to_dict() -> None:
    hit = SearchHit(
        uri="rag://corpus/c1/d1#text-0",
        text="hello",
        title="doc",
        score=1.0,
        metadata={"chunk_index": 0},
    )

    assert hit.to_dict()["uri"] == "rag://corpus/c1/d1#text-0"
```

```python
def test_section_result_model_to_dict() -> None:
    result = SectionResult(
        filename="doc",
        uri="rag://corpus/c1/d1#text-0",
        title="1 前言",
        text="hello",
        metadata={"chunk_index": 0},
        related_resource_uris=[],
        related_resources=[],
    )

    assert result.to_dict()["filename"] == "doc"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest -q tests/unit/test_internal_models.py`  
Expected: FAIL。

- [ ] **Step 3: 写最小实现**

```python
@dataclass(frozen=True)
class SearchHit:
    uri: str
    text: str
    title: str
    score: float
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "uri": self.uri,
            "text": self.text,
            "title": self.title,
            "score": self.score,
            "metadata": self.metadata,
        }
```

```python
@dataclass(frozen=True)
class SectionResult:
    filename: str
    uri: str
    title: str
    text: str
    metadata: dict[str, Any]
    related_resource_uris: list[str]
    related_resources: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {...}
```

然后在 service 内部用 model，handler 外层仍输出 dict。

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
uv run pytest -q tests/unit/test_internal_models.py
uv run pytest -q tests/unit/test_catalog_service.py tests/unit/test_hybrid_search.py
```

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add src/rag_mcp/catalog/models.py src/rag_mcp/retrieval/models.py src/rag_mcp/resources/models.py tests/unit/test_internal_models.py src/rag_mcp/catalog/service.py src/rag_mcp/retrieval/service.py src/rag_mcp/resources/service.py
git commit -m "refactor: add internal payload models for query services"
```

### Task 4: 固化 query/write 边界文档与回归

**Files:**
- Create: `docs/architecture/query-write-boundary.md`
- Verify: `tests/unit/test_indexing_services.py`
- Verify: `tests/unit/test_architecture_boundaries.py`
- Verify: `tests/unit/test_rebuild_multimodal.py`

- [ ] **Step 1: 写边界文档**

文档至少明确：
- `indexing/*` 为 write-side
- `catalog/resources/retrieval` 为 read-side
- 读路径不写 manifest/store
- 写路径不做 tool formatting

示例段落：

```markdown
## Read Path
- catalog: filename/section browse
- retrieval: search orchestration
- resources: rag:// fetch

## Write Path
- indexing: ingest, chunk, embed, persist, activate manifest
```

- [ ] **Step 2: 运行边界相关测试**

Run:

```bash
uv run pytest -q tests/unit/test_indexing_services.py tests/unit/test_architecture_boundaries.py
```

Expected: PASS。

- [ ] **Step 3: 运行关键回归**

Run:

```bash
uv run pytest -q tests/unit/test_catalog_service.py tests/unit/test_resource_service_multimodal.py tests/unit/test_hybrid_search.py tests/unit/test_rebuild_multimodal.py
```

Expected: PASS。

- [ ] **Step 4: 记录架构决策**

在变更说明中写清：
- 哪些模块属于 query-side
- 哪些模块属于 write-side
- 内部 model 的边界

- [ ] **Step 5: 提交**

```bash
git add docs/architecture/query-write-boundary.md tests/unit/test_indexing_services.py tests/unit/test_architecture_boundaries.py src/rag_mcp/indexing src/rag_mcp/catalog src/rag_mcp/resources src/rag_mcp/retrieval
git commit -m "docs: freeze query and write path boundaries"
```

## 3) Phase 3 验收

- [ ] `rebuild.py` 不再承载所有写路径职责。
- [ ] query-side 三个 service 边界稳定。
- [ ] 关键内部 payload 已 model 化。
- [ ] query/write 边界有文档和测试支撑。
- [ ] `uv run pytest -q tests/unit/test_indexing_services.py tests/unit/test_architecture_boundaries.py tests/unit/test_internal_models.py tests/unit/test_catalog_service.py tests/unit/test_resource_service_multimodal.py tests/unit/test_hybrid_search.py tests/unit/test_rebuild_multimodal.py` 全通过。

## 4) 签收记录

- [ ] Phase Owner: Pending
- [ ] QA/Reviewer: Pending
- [ ] Sign-off Date: Pending
- [ ] Sign-off Commit: Pending
- [ ] Notes: Pending

