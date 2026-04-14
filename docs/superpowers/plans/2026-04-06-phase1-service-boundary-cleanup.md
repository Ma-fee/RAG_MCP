# Phase 1 Service Boundary Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 收紧 `rag_mcp` 的 repository / service / transport 边界，在不改变 MCP tool 对外结构的前提下，把文件读取和目录查询核心逻辑从 handler 中移出。

**Architecture:** 新增 repository 层负责 manifest/store 读取与基础校验；`ResourceService`、`RetrievalService`、`CatalogQueryService` 只做业务逻辑与结果拼装；`ToolHandlers` 退化为参数适配和错误翻译层。Phase 1 不修改 URI 契约，也不统一 tool contract，只做边界清理。

**Tech Stack:** Python 3.13, pytest, dataclasses, pathlib, JSON store files

---

## 0) Plan Review

- [ ] 已确认本 Phase 不修改 `rag://` URI 契约。
- [ ] 已确认本 Phase 不修改 MCP tool 名称。
- [ ] 已确认本 Phase 不重写 `rebuild.py` 主流程。
- [ ] 已确认 `handlers.py` 对外成功返回结构与错误 dict 结构保持稳定。
- [ ] Reviewer: Pending
- [ ] Review Date: 2026-04-06

## 1) 文件规划

**Create**
- `src/rag_mcp/indexing/repositories.py`
- `src/rag_mcp/catalog/__init__.py`
- `src/rag_mcp/catalog/service.py`
- `tests/unit/test_repositories.py`
- `tests/unit/test_catalog_service.py`

**Modify**
- `src/rag_mcp/resources/service.py`
- `src/rag_mcp/retrieval/service.py`
- `src/rag_mcp/transport/handlers.py`
- `tests/unit/test_resource_service_multimodal.py`
- `tests/unit/test_hybrid_search.py`
- `tests/unit/test_handlers_dict.py`

## 2) 原子化 TDD Tasks

### Task 1: Repository 基础设施

**Files:**
- Create: `src/rag_mcp/indexing/repositories.py`
- Test: `tests/unit/test_repositories.py`

- [ ] **Step 1: 写失败测试**

```python
def test_resource_store_repository_get_returns_entry(tmp_path: Path) -> None:
    index_dir = tmp_path / "idx"
    index_dir.mkdir()
    (index_dir / "resource_store.json").write_text(
        json.dumps(
            {
                "entries": [
                    {"uri": "rag://corpus/c1/d1#image-0", "type": "image"},
                ]
            }
        ),
        encoding="utf-8",
    )

    repo = ResourceStoreRepository(index_dir=index_dir)

    assert repo.get("rag://corpus/c1/d1#image-0") == {
        "uri": "rag://corpus/c1/d1#image-0",
        "type": "image",
    }
```

再补：
- `test_active_index_repository_missing_file_raises`
- `test_keyword_store_repository_rejects_non_list_entries`
- `test_sections_mapping_repository_rejects_non_list_values`

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest -q tests/unit/test_repositories.py`  
Expected: FAIL，提示 `Repository` 类尚不存在。

- [ ] **Step 3: 写最小实现**

```python
class RepositoryError(RuntimeError):
    pass


class RepositoryNotFoundError(RepositoryError):
    pass


class RepositoryFormatError(RepositoryError):
    pass


def _read_json_dict(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise RepositoryNotFoundError(f"missing repository file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RepositoryFormatError(f"repository payload must be dict: {path}")
    return payload
```

```python
@dataclass(frozen=True)
class ActiveIndexRepository:
    data_dir: Path
    def load(self) -> dict[str, Any]:
        return _read_json_dict(self.data_dir / "active_index.json")
```

```python
@dataclass(frozen=True)
class KeywordStoreRepository:
    index_dir: Path
    def load(self) -> dict[str, Any]:
        payload = _read_json_dict(self.index_dir / "keyword_store.json")
        if not isinstance(payload.get("entries"), list):
            raise RepositoryFormatError("keyword_store.entries must be list")
        return payload
    def entries(self) -> list[dict[str, Any]]:
        return list(self.load()["entries"])
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest -q tests/unit/test_repositories.py`  
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add src/rag_mcp/indexing/repositories.py tests/unit/test_repositories.py
git commit -m "feat: add repository layer for active index and stores"
```

### Task 2: `ResourceService` 切换到 Repository

**Files:**
- Modify: `src/rag_mcp/resources/service.py`
- Modify/Test: `tests/unit/test_resource_service_multimodal.py`

- [ ] **Step 1: 写失败测试**

新增：

```python
def test_read_text_resource_merges_resource_metadata(tmp_path: Path) -> None:
    index_dir = tmp_path / "idx"
    corpus_id = "abc123"
    doc_id = "doc456"
    uri = f"rag://corpus/{corpus_id}/{doc_id}#text-0"

    _write_manifest(tmp_path, index_dir, corpus_id)
    _write_resource_store(index_dir, [])
    (index_dir / "keyword_store.json").write_text(
        json.dumps(
            {
                "corpus_id": corpus_id,
                "entries": [
                    {
                        "uri": uri,
                        "text": "hello world",
                        "title": "doc",
                        "metadata": {"section_title": "sec", "chunk_index": 0},
                        "resource_metadata": {"page_number": 3},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = ResourceService(data_dir=tmp_path).read(uri)

    assert result["metadata"]["page_number"] == 3
```

再补：
- manifest 缺失 -> `NO_ACTIVE_INDEX`
- manifest 顶层非法 -> `NO_ACTIVE_INDEX`
- keyword/resource store 缺失 -> `RESOURCE_NOT_FOUND`

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest -q tests/unit/test_resource_service_multimodal.py`  
Expected: FAIL，说明当前实现仍直接读文件或异常语义不完整。

- [ ] **Step 3: 写最小实现**

```python
class ResourceService:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = Path(data_dir)
        self.active_indexes = ActiveIndexRepository(self.data_dir)
```

```python
def _load_active_manifest(self) -> dict[str, Any]:
    try:
        return self.active_indexes.load()
    except RepositoryNotFoundError:
        raise ServiceException(
            ServiceError(
                code=ErrorCode.NO_ACTIVE_INDEX,
                message="当前没有活动索引",
                hint="请先调用 rag_rebuild_index",
            )
        )
```

```python
def _read_text_resource(self, uri: str, index_dir: Path) -> dict[str, Any]:
    entries = KeywordStoreRepository(index_dir=index_dir).entries()
    for entry in entries:
        if entry.get("uri") != uri:
            continue
        metadata = dict(entry.get("metadata", {}))
        if isinstance(entry.get("resource_metadata"), dict):
            metadata.update(entry["resource_metadata"])
        return {"uri": entry["uri"], "text": entry["text"], "metadata": metadata}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest -q tests/unit/test_resource_service_multimodal.py`  
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add src/rag_mcp/resources/service.py tests/unit/test_resource_service_multimodal.py
git commit -m "refactor: migrate resource service to repositories"
```

### Task 3: `RetrievalService` 切换到 `ActiveIndexRepository`

**Files:**
- Modify: `src/rag_mcp/retrieval/service.py`
- Modify/Test: `tests/unit/test_hybrid_search.py`

- [ ] **Step 1: 写失败测试**

新增：

```python
def test_search_without_active_index_raises_service_exception(tmp_path: Path) -> None:
    from rag_mcp.errors import ErrorCode, ServiceException
    from rag_mcp.retrieval.service import RetrievalService

    svc = RetrievalService(data_dir=tmp_path, embedding_provider=None)

    with pytest.raises(ServiceException) as exc:
        svc._load_active_manifest()

    assert exc.value.error.code == ErrorCode.NO_ACTIVE_INDEX
```

再补：
- manifest 非法时也抛 `NO_ACTIVE_INDEX`

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest -q tests/unit/test_hybrid_search.py`  
Expected: FAIL。

- [ ] **Step 3: 写最小实现**

```python
class RetrievalService:
    def __init__(self, data_dir: Path, embedding_provider: Any | None = None, reranker: Any | None = None, rerank_top_k_candidates: int = 20) -> None:
        self.data_dir = Path(data_dir)
        self.embedding_provider = embedding_provider
        self._reranker = reranker
        self._rerank_top_k_candidates = rerank_top_k_candidates
        self.active_indexes = ActiveIndexRepository(self.data_dir)

    def _load_active_manifest(self) -> dict[str, Any]:
        try:
            return self.active_indexes.load()
        except (RepositoryNotFoundError, RepositoryFormatError):
            raise ServiceException(
                ServiceError(
                    code=ErrorCode.NO_ACTIVE_INDEX,
                    message="当前没有活动索引",
                    hint="请先调用 rag_rebuild_index",
                )
            )
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest -q tests/unit/test_hybrid_search.py`  
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add src/rag_mcp/retrieval/service.py tests/unit/test_hybrid_search.py
git commit -m "refactor: migrate retrieval service manifest access to repository"
```

### Task 4: 抽取 `CatalogQueryService` 并瘦身 `ToolHandlers`

**Files:**
- Create: `src/rag_mcp/catalog/__init__.py`
- Create: `src/rag_mcp/catalog/service.py`
- Modify: `src/rag_mcp/transport/handlers.py`
- Create/Test: `tests/unit/test_catalog_service.py`
- Modify/Test: `tests/unit/test_handlers_dict.py`

- [ ] **Step 1: 写失败测试**

新增 `tests/unit/test_catalog_service.py`：

```python
def test_list_filenames_groups_entries_by_document(tmp_path: Path) -> None:
    data_dir = tmp_path
    index_dir = tmp_path / "idx"
    index_dir.mkdir()
    (data_dir / "active_index.json").write_text(
        json.dumps({"corpus_id": "c1", "index_dir": str(index_dir), "document_count": 1, "chunk_count": 2, "indexed_at": 123}),
        encoding="utf-8",
    )
    (index_dir / "keyword_store.json").write_text(
        json.dumps(
            {
                "entries": [
                    {"uri": "rag://corpus/c1/d1#text-0", "text": "hello", "title": "Spec", "metadata": {"relative_path": "spec.pdf", "file_type": "pdf", "chunk_index": 0, "section_title": "1 前言"}},
                    {"uri": "rag://corpus/c1/d1#text-1", "text": "world", "title": "Spec", "metadata": {"relative_path": "spec.pdf", "file_type": "pdf", "chunk_index": 1, "section_title": "2 系统结构"}},
                ]
            }
        ),
        encoding="utf-8",
    )

    service = CatalogQueryService(data_dir=data_dir, resources=ResourceService(data_dir))

    result = service.list_filenames()

    assert result["count"] == 1
    assert result["filenames"][0]["filename"] == "spec"
```

再补：
- `test_list_sections_uses_sections_mapping_when_present`
- `test_list_sections_falls_back_when_mapping_missing`
- `test_section_retrieval_resolves_related_resources`

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
uv run pytest -q tests/unit/test_catalog_service.py
uv run pytest -q tests/unit/test_handlers_dict.py
```

Expected: FAIL。

- [ ] **Step 3: 写最小实现**

在 `handlers.py` 中加入：

```python
from rag_mcp.catalog.service import CatalogQueryService

self.catalog = CatalogQueryService(self.data_dir, resources=self.resources)
```

并把三个方法改成薄壳：

```python
def list_filenames(self) -> dict:
    try:
        return self.catalog.list_filenames()
    except ServiceException as exc:
        return {"error": exc.error.code.value, "message": exc.error.message}
```

```python
def list_sections(self, filename: str) -> dict:
    if not filename or not filename.strip():
        return {"error": "missing_filename", "message": "filename 不能为空"}
    try:
        return self.catalog.list_sections(filename.strip())
    except ServiceException as exc:
        return {"error": exc.error.code.value, "message": exc.error.message}
```

```python
def section_retrieval(self, section_title: list[str], filename: str) -> dict:
    if not filename or not filename.strip():
        return {"error": "missing_filename", "message": "filename 不能为空"}
    normalized_titles = [item.strip() for item in section_title if item and item.strip()]
    if not normalized_titles:
        return {"error": "missing_section_title", "message": "section_title 不能为空"}
    try:
        return self.catalog.section_retrieval(section_title=normalized_titles, filename=filename.strip())
    except ServiceException as exc:
        return {"error": exc.error.code.value, "message": exc.error.message}
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
uv run pytest -q tests/unit/test_catalog_service.py
uv run pytest -q tests/unit/test_handlers_dict.py
```

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add src/rag_mcp/catalog src/rag_mcp/transport/handlers.py tests/unit/test_catalog_service.py tests/unit/test_handlers_dict.py
git commit -m "refactor: extract catalog query service from handlers"
```

### Task 5: Phase 1 回归收口

**Files:**
- Verify: `tests/unit/test_repositories.py`
- Verify: `tests/unit/test_resource_service_multimodal.py`
- Verify: `tests/unit/test_hybrid_search.py`
- Verify: `tests/unit/test_catalog_service.py`
- Verify: `tests/unit/test_handlers_dict.py`

- [ ] **Step 1: 运行单项回归**

Run:

```bash
uv run pytest -q tests/unit/test_repositories.py
uv run pytest -q tests/unit/test_resource_service_multimodal.py
uv run pytest -q tests/unit/test_hybrid_search.py
uv run pytest -q tests/unit/test_catalog_service.py
uv run pytest -q tests/unit/test_handlers_dict.py
```

Expected: 全部 PASS。

- [ ] **Step 2: 运行聚合回归**

Run:

```bash
uv run pytest -q tests/unit/test_repositories.py tests/unit/test_resource_service_multimodal.py tests/unit/test_hybrid_search.py tests/unit/test_catalog_service.py tests/unit/test_handlers_dict.py
```

Expected: PASS。

- [ ] **Step 3: 清理边界**

确认：
- `handlers.py` 不再保留 `_group_entries_by_document`
- `handlers.py` 不再保留 `_load_sections_mapping`
- 相关逻辑已移入 `CatalogQueryService`

- [ ] **Step 4: 记录结果**

在 PR / 变更说明中写明：
- 新增 repository 层
- `ResourceService` / `RetrievalService` 不再直接做文件 I/O
- `CatalogQueryService` 已抽出
- handler 仅做 adapter

- [ ] **Step 5: 提交**

```bash
git add src/rag_mcp tests
git commit -m "test: add phase1 service boundary regression coverage"
```

## 3) Phase 1 验收

- [ ] `src/rag_mcp/indexing/repositories.py` 已存在并被测试覆盖。
- [ ] `ResourceService` 不再直接 `json.loads(...)` store 文件。
- [ ] `RetrievalService` 不再直接读取 `active_index.json`。
- [ ] `CatalogQueryService` 已承接目录/章节查询核心逻辑。
- [ ] `ToolHandlers` 已瘦身为 transport adapter。
- [ ] `uv run pytest -q tests/unit/test_repositories.py tests/unit/test_resource_service_multimodal.py tests/unit/test_hybrid_search.py tests/unit/test_catalog_service.py tests/unit/test_handlers_dict.py` 全通过。

## 4) 签收记录

- [ ] Phase Owner: Pending
- [ ] QA/Reviewer: Pending
- [ ] Sign-off Date: Pending
- [ ] Sign-off Commit: Pending
- [ ] Notes: Pending

