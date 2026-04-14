# Spec: Phase 1 服务边界收敛与 Repository 抽取

**日期**: 2026-04-06
**范围**: repository 基础设施、`ResourceService`/`RetrievalService` 解耦文件读取、`CatalogQueryService` 抽取、transport handler 瘦身、Phase 1 回归测试收口

---

## 1. 背景与目标

当前 `rag_mcp` 已具备可用的索引、检索与 `rag://` 读回能力，但多个模块已经同时承担了“业务逻辑 + 文件存取 + 错误翻译 + 输出组装”职责，边界已经开始混杂。

当前主要问题：
- service 层直接读取 `active_index.json`、`keyword_store.json`、`resource_store.json`
- `ToolHandlers` 里包含目录分组、章节映射回退、related resource enrich 等领域逻辑
- manifest/store 读取逻辑散落在多个文件中，异常语义不一致
- 后续若要引入缓存、schema 校验、multi-index 选择，会出现多点修改与重复实现

**Phase 1 目标** 不是改协议，也不是改功能，而是先把边界收紧：
- 文件读取统一进入 repository 层
- service 层只做业务判断与结果拼装
- transport 层只做参数适配和错误翻译
- 目录/章节查询逻辑从 `ToolHandlers` 中抽出
- 对外 MCP tool 的返回结构保持不变

**非目标**：
- 不修改 `rag://` URI 契约
- 不修改 MCP tool 名称
- 不重写 `rebuild.py`
- 不引入 Pydantic/DTO 重构
- 不处理 experiment pipeline 复用
- 不调整 FastMCP transport surface

---

## 2. 总体边界设计

Phase 1 之后的分层目标如下：

### Repository 层

负责：
- 文件存在性检查
- JSON 读取
- 顶层结构校验
- store payload 的轻量访问

不负责：
- 业务错误码
- `ServiceException`
- transport dict 输出

### Service 层

负责：
- 业务规则
- active index / corpus 校验
- 搜索编排
- 结果拼装
- repository 异常翻译为 `ServiceException`

不负责：
- 直接文件 I/O
- transport dict 错误格式

### Transport 层

负责：
- 参数校验
- 调用 service
- `ServiceException` -> `{"error": "...", "message": "..."}` 翻译

不负责：
- 文档分组
- section mapping fallback
- related resource enrich

---

## 3. Task 1: 新增 Repository 基础设施

### 3.1 任务目标

把 `active_index.json`、`keyword_store.json`、`resource_store.json`、`sections_mapping.json` 的读取逻辑集中到一个基础设施文件里，后续由 service 统一依赖这个文件。

### 3.2 涉及文件

- 新增: `src/rag_mcp/indexing/repositories.py`
- 保留不改: `src/rag_mcp/indexing/manifest.py`
- 新增测试: `tests/unit/test_repositories.py`

### 3.3 具体改动

新增以下异常与 repository：

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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


@dataclass(frozen=True)
class ActiveIndexRepository:
    data_dir: Path

    def load(self) -> dict[str, Any]:
        return _read_json_dict(self.data_dir / "active_index.json")


@dataclass(frozen=True)
class KeywordStoreRepository:
    index_dir: Path

    def load(self) -> dict[str, Any]:
        payload = _read_json_dict(self.index_dir / "keyword_store.json")
        entries = payload.get("entries")
        if not isinstance(entries, list):
            raise RepositoryFormatError("keyword_store.entries must be list")
        return payload

    def entries(self) -> list[dict[str, Any]]:
        return list(self.load()["entries"])


@dataclass(frozen=True)
class ResourceStoreRepository:
    index_dir: Path

    def load(self) -> dict[str, Any]:
        payload = _read_json_dict(self.index_dir / "resource_store.json")
        entries = payload.get("entries")
        if not isinstance(entries, list):
            raise RepositoryFormatError("resource_store.entries must be list")
        return payload

    def entries(self) -> list[dict[str, Any]]:
        return list(self.load()["entries"])

    def get(self, uri: str) -> dict[str, Any] | None:
        for entry in self.entries():
            if entry.get("uri") == uri:
                return dict(entry)
        return None


@dataclass(frozen=True)
class SectionsMappingRepository:
    index_dir: Path

    def load(self) -> dict[str, list[str]]:
        payload = _read_json_dict(self.index_dir / "sections_mapping.json")
        normalized: dict[str, list[str]] = {}
        for key, value in payload.items():
            if not isinstance(key, str) or not isinstance(value, list):
                raise RepositoryFormatError("sections_mapping payload invalid")
            normalized[key] = [str(item) for item in value]
        return normalized
```

### 3.4 行为规范

| 场景 | 期望结果 |
|------|----------|
| `active_index.json` 不存在 | 抛 `RepositoryNotFoundError` |
| store 文件不存在 | 抛 `RepositoryNotFoundError` |
| 顶层 JSON 不是 dict | 抛 `RepositoryFormatError` |
| `entries` 字段缺失或不是 list | 抛 `RepositoryFormatError` |
| `sections_mapping.json` value 不是 list | 抛 `RepositoryFormatError` |
| `ResourceStoreRepository.get(uri)` 未命中 | 返回 `None` |

### 3.5 为什么 `manifest.py` 先保留

Phase 1 的目标是“边界收敛”，不是“一次性全仓库替换底层读法”。因此：
- `read_active_manifest()`
- `write_active_manifest_atomic()`

这两个函数在 Phase 1 内先保留，避免影响 `rebuild.py` 等更大范围调用点。repository 是新增基础设施，先让 service 迁移过去。

### 3.6 先写的测试

测试文件：`tests/unit/test_repositories.py`

至少补这些场景：
- `test_active_index_repository_missing_file_raises`
- `test_keyword_store_repository_rejects_non_dict_payload`
- `test_keyword_store_repository_rejects_non_list_entries`
- `test_resource_store_repository_get_returns_entry`
- `test_resource_store_repository_get_returns_none_when_missing`
- `test_sections_mapping_repository_rejects_non_list_values`

建议最小测试样例：

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

    result = repo.get("rag://corpus/c1/d1#image-0")

    assert result == {"uri": "rag://corpus/c1/d1#image-0", "type": "image"}
```

### 3.7 实施顺序

1. 新建 `src/rag_mcp/indexing/repositories.py`
2. 先把 repository 的异常和 `_read_json_dict()` 写完
3. 再补四个 repository 类
4. 先写 `tests/unit/test_repositories.py`
5. 跑 `uv run pytest -q tests/unit/test_repositories.py`

### 3.8 完成标准

Task 1 完成后必须满足：
- repository 文件已存在
- 四类 repository 都有最小读取接口
- 文件缺失和格式非法场景有稳定异常
- `tests/unit/test_repositories.py` 通过

---

## 4. Task 2: `ResourceService` 改为依赖 Repository

### 4.1 任务目标

`ResourceService` 必须停止直接读取：
- `active_index.json`
- `resource_store.json`
- `keyword_store.json`

改为统一依赖 Task 1 中的 repository。

### 4.2 涉及文件

- 修改: `src/rag_mcp/resources/service.py`
- 依赖: `src/rag_mcp/indexing/repositories.py`
- 回归测试: `tests/unit/test_resource_service_multimodal.py`

### 4.3 当前问题

当前 `src/rag_mcp/resources/service.py` 直接：
- 调 `read_active_manifest(...)`
- `json.loads(...)`
- 手动遍历 `resource_store["entries"]`
- 手动遍历 `keyword_store["entries"]`

这导致 service 同时承担了 I/O 和业务逻辑。

### 4.4 具体改法

建议把 `ResourceService` 收成下面这种结构：

```python
from rag_mcp.indexing.repositories import (
    ActiveIndexRepository,
    KeywordStoreRepository,
    RepositoryFormatError,
    RepositoryNotFoundError,
    ResourceStoreRepository,
)


class ResourceService:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = Path(data_dir)
        self.active_indexes = ActiveIndexRepository(self.data_dir)

    def read(self, uri: str) -> dict[str, Any]:
        parsed = parse_rag_uri(uri)
        manifest = self._load_active_manifest()
        index_dir = self._validate_corpus(parsed, manifest)

        if parsed.fragment_type in ("image", "table"):
            return self._read_structured_resource(uri=uri, index_dir=index_dir)

        return self._read_text_resource(uri=uri, index_dir=index_dir)

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
        except RepositoryFormatError:
            raise ServiceException(
                ServiceError(
                    code=ErrorCode.NO_ACTIVE_INDEX,
                    message="活动索引格式无效",
                    hint="请重新构建索引",
                )
            )

    def _validate_corpus(self, parsed: ParsedRagUri, manifest: dict[str, Any]) -> Path:
        if manifest["corpus_id"] != parsed.corpus_id:
            raise ServiceException(
                ServiceError(
                    code=ErrorCode.RESOURCE_NOT_FOUND,
                    message="资源不在当前活动索引中",
                    hint="请确认 rag:// URI 与活动索引匹配",
                )
            )
        return Path(manifest["index_dir"])

    def _read_structured_resource(self, uri: str, index_dir: Path) -> dict[str, Any]:
        try:
            repository = ResourceStoreRepository(index_dir=index_dir)
            entry = repository.get(uri)
        except (RepositoryNotFoundError, RepositoryFormatError):
            raise ServiceException(
                ServiceError(
                    code=ErrorCode.RESOURCE_NOT_FOUND,
                    message="未找到对应资源",
                    hint="请确认资源索引存在且格式有效",
                )
            )

        if entry is None:
            raise ServiceException(
                ServiceError(
                    code=ErrorCode.RESOURCE_NOT_FOUND,
                    message="未找到对应资源",
                    hint="请确认 uri 来源于最新检索结果",
                )
            )
        return dict(entry)

    def _read_text_resource(self, uri: str, index_dir: Path) -> dict[str, Any]:
        try:
            repository = KeywordStoreRepository(index_dir=index_dir)
            entries = repository.entries()
        except (RepositoryNotFoundError, RepositoryFormatError):
            raise ServiceException(
                ServiceError(
                    code=ErrorCode.RESOURCE_NOT_FOUND,
                    message="未找到对应资源",
                    hint="请确认索引存在且未损坏，必要时重建索引",
                )
            )

        for entry in entries:
            if entry.get("uri") != uri:
                continue

            metadata = dict(entry.get("metadata", {}))
            resource_metadata = entry.get("resource_metadata")
            if isinstance(resource_metadata, dict):
                metadata.update(resource_metadata)

            return {
                "uri": entry["uri"],
                "text": entry["text"],
                "metadata": metadata,
            }

        raise ServiceException(
            ServiceError(
                code=ErrorCode.RESOURCE_NOT_FOUND,
                message="未找到对应资源",
                hint="请确认 uri 来源于最新检索结果",
            )
        )
```

### 4.5 职责边界

`ResourceService` 保留职责：
- 解析 `rag://` URI
- 校验当前 active index 与 `corpus_id` 是否一致
- 根据 fragment 类型选择 resource store 或 keyword store
- 合并 `resource_metadata`
- 将 repository 异常翻译成 `ServiceException`

`ResourceService` 移除职责：
- 直接 `json.loads(...)`
- 直接读取 store 文件
- 直接定义底层文件缺失时的 I/O 语义

### 4.6 对外行为要求

以下返回结构必须保持不变。

文本资源：

```python
{
    "uri": entry["uri"],
    "text": entry["text"],
    "metadata": metadata,
}
```

图片/表格资源：
- 继续返回 `resource_store.json` 中的原始 dict

### 4.7 先写的测试

保留并扩展：`tests/unit/test_resource_service_multimodal.py`

至少补这些场景：
- 无 active index 时抛 `NO_ACTIVE_INDEX`
- active manifest 非法时抛 `NO_ACTIVE_INDEX`
- `corpus_id` 不匹配时抛 `RESOURCE_NOT_FOUND`
- image/table 路径继续从 `resource_store.json` 读取
- text 路径继续从 `keyword_store.json` 读取
- `resource_metadata` 会 merge 到返回的 `metadata`
- store 缺失/格式非法时错误语义不变

建议新增一个 merge 测试：

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

    svc = ResourceService(data_dir=tmp_path)

    result = svc.read(uri)

    assert result["metadata"]["section_title"] == "sec"
    assert result["metadata"]["page_number"] == 3
```

### 4.8 实施顺序

1. 先引入 repository import
2. 把 `read()` 拆成 `_load_active_manifest()`、`_validate_corpus()`、`_read_structured_resource()`、`_read_text_resource()`
3. 删掉 `json.loads(...)` 直读逻辑
4. 先跑 `uv run pytest -q tests/unit/test_resource_service_multimodal.py`
5. 再与 Task 1 一起回归

### 4.9 完成标准

Task 2 完成后必须满足：
- `ResourceService` 不再直接 `json.loads(...)`
- `ResourceService` 不再直接读取 store 文件
- image/table/text 返回结构不变
- `tests/unit/test_resource_service_multimodal.py` 通过

---

## 5. Task 3: `RetrievalService` 改为依赖 `ActiveIndexRepository`

### 5.1 任务目标

`RetrievalService` 不再直接读取 `active_index.json`，而是通过 repository 获取 active index 上下文。

### 5.2 涉及文件

- 修改: `src/rag_mcp/retrieval/service.py`
- 依赖: `src/rag_mcp/indexing/repositories.py`
- 回归测试: `tests/unit/test_hybrid_search.py`

### 5.3 当前问题

当前 `src/rag_mcp/retrieval/service.py` 的 `_load_active_manifest()` 仍然直接依赖：

```python
manifest = read_active_manifest(self.data_dir / "active_index.json")
```

这意味着 retrieval service 仍然自己处理 I/O 入口，不利于后续统一异常语义。

### 5.4 具体改法

建议最小改法，不碰 hybrid 行为本身，只切换 manifest 来源：

```python
from rag_mcp.indexing.repositories import (
    ActiveIndexRepository,
    RepositoryFormatError,
    RepositoryNotFoundError,
)


class RetrievalService:
    def __init__(
        self,
        data_dir: Path,
        embedding_provider: Any | None = None,
        reranker: Any | None = None,
        rerank_top_k_candidates: int = 20,
    ) -> None:
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

如需进一步收口，可加一个轻量 helper：

```python
def _active_index_dir(self) -> Path:
    manifest = self._load_active_manifest()
    return Path(manifest["index_dir"])
```

但 Phase 1 不强制拆更多 helper，只要求不再直接读 manifest 文件。

### 5.5 职责边界

`RetrievalService` 保留职责：
- keyword / vector / hybrid-rerank 搜索编排
- query splitting
- RRF 融合
- reranker 接入
- 结果投影

`RetrievalService` 移除职责：
- 自行发现当前 active index 文件
- 自行处理 manifest 缺失/格式非法的 I/O 入口

### 5.6 行为规范

| 场景 | 期望结果 |
|------|----------|
| 无 active index | 抛 `ServiceException(NO_ACTIVE_INDEX)` |
| manifest 非法 | 抛 `ServiceException(NO_ACTIVE_INDEX)` |
| 无 embedding provider | vector path 返回空结果，不抛异常 |
| 无 `chroma/` 目录 | vector path 返回空结果，不抛异常 |
| query splitter LLM 不可用 | 回退到 heuristic，不改变返回结构 |

### 5.7 对外行为要求

以下字段必须保持不变：
- `query`
- `mode`
- `top_k`
- `result_count`
- `results`

hybrid 搜索仍默认走 `_search_hybrid_rerank()`。

### 5.8 先写的测试

继续使用：`tests/unit/test_hybrid_search.py`

至少补这些场景：
- `test_search_without_active_index_raises_service_exception`
- `test_search_with_invalid_manifest_raises_service_exception`
- `test_vector_search_without_embedding_provider_returns_empty_results`
- `test_split_query_falls_back_when_llm_unavailable`

如果本轮只做最小切换，至少要新增前两个测试，确保 active manifest 的异常语义稳定。

### 5.9 实施顺序

1. 先引入 `ActiveIndexRepository`
2. 只改 `_load_active_manifest()`
3. 跑 `uv run pytest -q tests/unit/test_hybrid_search.py`
4. 不要在这一轮重写 hybrid/search 主流程

### 5.10 完成标准

Task 3 完成后必须满足：
- `RetrievalService` 不再直接读 `active_index.json`
- hybrid/keyword/vector 的对外结构不变
- `tests/unit/test_hybrid_search.py` 通过

---

## 6. Task 4: 抽取 `CatalogQueryService` 并让 `ToolHandlers` 变薄

### 6.1 任务目标

把目录/章节查询相关逻辑从 `ToolHandlers` 中拆出来，让 handler 只承担 transport adapter 职责。

### 6.2 涉及文件

- 新增: `src/rag_mcp/catalog/__init__.py`
- 新增: `src/rag_mcp/catalog/service.py`
- 修改: `src/rag_mcp/transport/handlers.py`
- 新增测试: `tests/unit/test_catalog_service.py`
- 保留并扩展: `tests/unit/test_handlers_dict.py`

### 6.3 当前问题

当前 `src/rag_mcp/transport/handlers.py` 同时承担了：
- 文档分组
- section mapping 读取
- mapping 缺失 fallback
- section title 校验
- `related_resource_uris` enrich 为 `related_resources`

这明显已经超出 transport adapter 的职责。

### 6.4 新服务的目标职责

`CatalogQueryService` 负责：
- 文档分组
- 文件名列表查询
- section title 列表查询
- section retrieval
- `related_resource_uris` enrich 为 `related_resources`

`ToolHandlers` 只负责：
- 参数校验
- service 调用
- `ServiceException` -> dict 错误翻译

### 6.5 `CatalogQueryService` 建议类

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rag_mcp.resources.service import ResourceService


@dataclass
class CatalogQueryService:
    data_dir: Path
    resources: ResourceService

    def list_filenames(self) -> dict[str, Any]: ...
    def list_sections(self, filename: str) -> dict[str, Any]: ...
    def section_retrieval(
        self,
        section_title: list[str],
        filename: str,
    ) -> dict[str, Any]: ...
```

### 6.6 `CatalogQueryService` 建议内部 helper

```python
def _active_index_dir(self) -> Path: ...
def _keyword_entries(self) -> list[dict[str, Any]]: ...
def _group_entries_by_document(
    self,
    entries: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]: ...
def _load_sections_mapping(self) -> dict[str, list[str]]: ...
def _extract_sections_from_entries(self, entries: list[dict[str, Any]]) -> list[str]: ...
def _resolve_related_resources(self, related_uris: list[str]) -> list[dict[str, Any]]: ...
```

建议保留这些 helper，但只放在 `CatalogQueryService` 内，不再放在 handler 里。

### 6.7 具体改法

建议先新建 `src/rag_mcp/catalog/service.py`，把现在 handler 中以下逻辑搬进去：
- `_group_entries_by_document`
- `_load_sections_mapping`
- `_extract_sections_from_entries`
- `_resolve_related_resources`
- `list_filenames`
- `list_sections`
- `section_retrieval`

#### `CatalogQueryService` 的最小骨架

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rag_mcp.errors import ErrorCode, ServiceError, ServiceException
from rag_mcp.indexing.repositories import (
    ActiveIndexRepository,
    KeywordStoreRepository,
    RepositoryFormatError,
    RepositoryNotFoundError,
    SectionsMappingRepository,
)
from rag_mcp.resources.service import ResourceService


@dataclass
class CatalogQueryService:
    data_dir: Path
    resources: ResourceService

    def __post_init__(self) -> None:
        self.data_dir = Path(self.data_dir)
        self.active_indexes = ActiveIndexRepository(self.data_dir)

    def list_filenames(self) -> dict[str, Any]:
        entries = self._keyword_entries()
        grouped = self._group_entries_by_document(entries)

        filenames = []
        for doc_key, payload in sorted(grouped.items(), key=lambda item: item[0]):
            filenames.append(
                {
                    "filename": doc_key,
                    "file_type": payload["file_type"],
                    "chunk_count": len(payload["entries"]),
                }
            )

        return {"count": len(filenames), "filenames": filenames}

    def list_sections(self, filename: str) -> dict[str, Any]:
        normalized_filename = filename.strip()
        entries = self._keyword_entries()
        grouped = self._group_entries_by_document(entries)
        doc_payload = grouped.get(normalized_filename)
        if doc_payload is None:
            raise ServiceException(
                ServiceError(
                    code=ErrorCode.RESOURCE_NOT_FOUND,
                    message=f"未找到文档: {normalized_filename}",
                    hint="请先调用 list_filenames 确认文件名",
                )
            )

        sections_mapping = self._load_sections_mapping()
        sections = sections_mapping.get(normalized_filename)
        if sections is None:
            sections = self._extract_sections_from_entries(doc_payload["entries"])

        if not sections:
            raise ServiceException(
                ServiceError(
                    code=ErrorCode.RESOURCE_NOT_FOUND,
                    message=f"未找到文档章节: {normalized_filename}",
                    hint="请确认索引包含 section_title 元数据",
                )
            )

        return {normalized_filename: sections}

    def section_retrieval(
        self,
        section_title: list[str],
        filename: str,
    ) -> dict[str, Any]:
        normalized_filename = filename.strip()
        normalized_titles = [item.strip() for item in section_title if item and item.strip()]

        entries = self._keyword_entries()
        grouped = self._group_entries_by_document(entries)
        doc_payload = grouped.get(normalized_filename)
        if doc_payload is None:
            raise ServiceException(
                ServiceError(
                    code=ErrorCode.RESOURCE_NOT_FOUND,
                    message=f"未找到文档: {normalized_filename}",
                    hint="请先调用 list_filenames 确认文件名",
                )
            )

        sections_mapping = self._load_sections_mapping()
        valid_titles = sections_mapping.get(normalized_filename)
        if valid_titles is None:
            valid_titles = self._extract_sections_from_entries(doc_payload["entries"])

        invalid_titles = [item for item in normalized_titles if item not in set(valid_titles)]
        if invalid_titles:
            raise ServiceException(
                ServiceError(
                    code=ErrorCode.RESOURCE_NOT_FOUND,
                    message="title 必须与 list_sections 返回的章节标题完全一致",
                    hint="请使用 list_sections 返回值作为 section_title",
                    details={"invalid_titles": ",".join(invalid_titles)},
                )
            )

        uri_to_entry = {
            str(entry.get("uri", "")): entry
            for entry in doc_payload["entries"]
            if entry.get("uri")
        }

        matched_results: list[dict[str, Any]] = []
        for entry in doc_payload["entries"]:
            metadata = entry.get("metadata", {})
            entry_section_title = str(metadata.get("section_title", "")).strip()
            if entry_section_title not in set(normalized_titles):
                continue

            related_uris = uri_to_entry.get(str(entry.get("uri", "")), {}).get(
                "related_resource_uris",
                [],
            )
            matched_results.append(
                {
                    "filename": normalized_filename,
                    "uri": entry.get("uri"),
                    "title": entry_section_title,
                    "text": entry.get("text", ""),
                    "metadata": metadata,
                    "related_resource_uris": related_uris,
                    "related_resources": self._resolve_related_resources(related_uris),
                }
            )

        matched_results.sort(
            key=lambda item: int(item.get("metadata", {}).get("chunk_index", 0))
        )

        return {
            "filename": normalized_filename,
            "requested_section_titles": normalized_titles,
            "result_count": len(matched_results),
            "results": matched_results,
        }
```

### 6.8 `ToolHandlers` 的具体改法

迁移后，`src/rag_mcp/transport/handlers.py` 的 `__init__()` 增加一个字段：

```python
from rag_mcp.catalog.service import CatalogQueryService

self.catalog = CatalogQueryService(self.data_dir, resources=self.resources)
```

然后这几个方法改成薄壳：

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
        return self.catalog.section_retrieval(
            section_title=normalized_titles,
            filename=filename.strip(),
        )
    except ServiceException as exc:
        return {"error": exc.error.code.value, "message": exc.error.message}
```

重构后，`handlers.py` 里原来那几个大的私有方法就应该可以删掉了，或者最多保留一个统一错误翻译 helper：

```python
def _service_error_dict(self, exc: ServiceException) -> dict[str, str]:
    return {"error": exc.error.code.value, "message": exc.error.message}
```

### 6.9 `CatalogQueryService` 的具体行为要求

#### `list_filenames()`

- 按 `metadata.relative_path` 的 stem 分组
- 每组返回：

```python
{
    "filename": "...",
    "file_type": "...",
    "chunk_count": 3,
}
```

- 最终结构必须保持：

```python
{
    "count": len(filenames),
    "filenames": [...],
}
```

#### `list_sections(filename)`

- 先确认 `filename` 对应文档存在
- 优先读取 `sections_mapping.json`
- 如果 mapping 缺失，fallback 到 keyword entries 中的 `metadata.section_title`
- 返回结构保持现状：

```python
{normalized_filename: sections}
```

#### `section_retrieval(section_title, filename)`

- 先确认 `filename` 对应文档存在
- 校验 title 必须属于指定文档
- 返回已排序 chunk
- 排序键继续使用 `metadata.chunk_index`
- 同时带回：
  - `related_resource_uris`
  - `related_resources`

最终结构必须保持现状：

```python
{
    "filename": normalized_filename,
    "requested_section_titles": normalized_titles,
    "result_count": len(matched_results),
    "results": matched_results,
}
```

### 6.10 错误语义建议

这一轮不改 handler 输出结构，但 service 内部建议统一抛 `ServiceException`，handler 再转 dict。

建议对应关系如下：

| 场景 | service 层建议 | handler 层返回 |
|------|----------------|----------------|
| active index 缺失 | `NO_ACTIVE_INDEX` | `{"error": "NO_ACTIVE_INDEX", "message": "当前没有活动索引"}` |
| filename 不存在 | `RESOURCE_NOT_FOUND` | `{"error": "RESOURCE_NOT_FOUND", "message": "未找到文档: xxx"}` |
| section title 非法 | `RESOURCE_NOT_FOUND` + details | `{"error": "RESOURCE_NOT_FOUND", "message": "title 必须与 list_sections 返回的章节标题完全一致"}` |

如果要完全保留当前 handler 的 `invalid_filename` / `invalid_title` 字面值，需要在 Phase 1 明确“不做这一项”，否则就接受内部错误码收敛到 `ServiceException` 体系。当前建议是：**Phase 1 先保留 handler 输出格式稳定，不强制保留旧的自定义 error literal。**

### 6.11 建议先写的测试

这一步建议两层测试。

第一层：新增 `tests/unit/test_catalog_service.py`，覆盖核心查询逻辑。

至少补这些场景：
1. `list_filenames()` 正常返回 `filename` / `file_type` / `chunk_count`
2. `list_sections()` 在 mapping 存在时使用 mapping
3. `list_sections()` 在 mapping 缺失时 fallback 到 entries 提取
4. `section_retrieval()` 能按 `section_title` 过滤结果
5. `section_retrieval()` 能带回 `related_resource_uris` 和 `related_resources`
6. `section_retrieval()` 对非法 title 返回结构化错误

第二层：保留 `tests/unit/test_handlers_dict.py`，验证 handler 输出格式没变。

最关键的是确认：
- 仍然返回 `{"error": "...", "message": "..."}` 这种 dict
- `list_sections()` 返回值结构没变
- `section_retrieval()` 返回键名没变

### 6.12 测试样例建议

`tests/unit/test_catalog_service.py` 里可以先写最小 happy path：

```python
def test_list_filenames_groups_entries_by_document(tmp_path: Path) -> None:
    data_dir = tmp_path
    index_dir = tmp_path / "idx"
    index_dir.mkdir()

    (data_dir / "active_index.json").write_text(
        json.dumps(
            {
                "corpus_id": "c1",
                "index_dir": str(index_dir),
                "document_count": 1,
                "chunk_count": 2,
                "indexed_at": 123,
            }
        ),
        encoding="utf-8",
    )
    (index_dir / "keyword_store.json").write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "uri": "rag://corpus/c1/d1#text-0",
                        "text": "hello",
                        "title": "Spec",
                        "metadata": {
                            "relative_path": "spec.pdf",
                            "file_type": "pdf",
                            "chunk_index": 0,
                            "section_title": "1 前言",
                        },
                    },
                    {
                        "uri": "rag://corpus/c1/d1#text-1",
                        "text": "world",
                        "title": "Spec",
                        "metadata": {
                            "relative_path": "spec.pdf",
                            "file_type": "pdf",
                            "chunk_index": 1,
                            "section_title": "2 系统结构",
                        },
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    service = CatalogQueryService(data_dir=data_dir, resources=ResourceService(data_dir))

    result = service.list_filenames()

    assert result["count"] == 1
    assert result["filenames"][0]["filename"] == "spec"
    assert result["filenames"][0]["chunk_count"] == 2
```

fallback 测试：

```python
def test_list_sections_falls_back_when_mapping_missing(tmp_path: Path) -> None:
    ...
    result = service.list_sections("spec")
    assert result == {"spec": ["1 前言", "2 系统结构"]}
```

### 6.13 建议的实现顺序

1. 先新建 `src/rag_mcp/catalog/service.py`
2. 先不改 handler，先把 `CatalogQueryService` 单测跑通
3. 再改 `src/rag_mcp/transport/handlers.py`
4. 跑：

```bash
uv run pytest -q tests/unit/test_catalog_service.py
uv run pytest -q tests/unit/test_handlers_dict.py
```

5. 最后再跑：

```bash
uv run pytest -q tests/unit/test_catalog_service.py tests/unit/test_handlers_dict.py tests/unit/test_resource_service_multimodal.py tests/unit/test_hybrid_search.py
```

### 6.14 完成标准

Task 4 完成后必须满足：
- `src/rag_mcp/transport/handlers.py` 不再包含文档分组和 section 查询核心逻辑
- 新增 `CatalogQueryService`
- `list_filenames` / `list_sections` / `section_retrieval` 的对外返回结构不变
- `handlers.py` 的方法更接近 transport adapter
- 新增目录查询服务测试
- 现有 handler 测试不回归

---

## 7. Task 5: Phase 1 回归测试与验收收口

### 7.1 任务目标

证明本轮只是边界收敛，不是功能重写。重点是“内部结构变了，但对外行为没回归”。

### 7.2 涉及文件

- `tests/unit/test_repositories.py`
- `tests/unit/test_resource_service_multimodal.py`
- `tests/unit/test_hybrid_search.py`
- `tests/unit/test_catalog_service.py`
- `tests/unit/test_handlers_dict.py`

### 7.3 每个测试文件的职责

#### `tests/unit/test_repositories.py`

证明 repository 基础设施可靠：
- 文件缺失有稳定异常
- JSON 顶层结构错误有稳定异常
- `entries` 校验存在
- mapping 校验存在
- `ResourceStoreRepository.get()` 行为明确

#### `tests/unit/test_resource_service_multimodal.py`

证明 `ResourceService` 解耦 I/O 后行为不变：
- text/image/table 路径仍可读
- active index 缺失或非法时错误稳定
- `resource_metadata` 仍会 merge

#### `tests/unit/test_hybrid_search.py`

证明 `RetrievalService` 只改 manifest 依赖，不改搜索编排：
- search 仍默认走 `hybrid_rerank`
- reranker fallback 不变
- 无 active index / manifest 非法时错误稳定

#### `tests/unit/test_catalog_service.py`

证明目录查询逻辑已经真正从 handler 中拆出来：
- 文档分组
- section mapping 使用
- fallback 提取
- related resources enrich
- 非法 title 校验

#### `tests/unit/test_handlers_dict.py`

证明 handler 仍是 transport adapter，dict 结构没有回归：
- `list_filenames()` 返回 `count` + `filenames`
- `list_sections()` 返回 `{filename: sections}` 或 error dict
- `section_retrieval()` 返回 `result_count` + `results`
- 错误输出仍为 `{"error": "...", "message": "..."}` 结构

### 7.4 验证顺序

建议按依赖顺序跑，而不是一次性全跑。

先单测各 task：

```bash
uv run pytest -q tests/unit/test_repositories.py
uv run pytest -q tests/unit/test_resource_service_multimodal.py
uv run pytest -q tests/unit/test_hybrid_search.py
uv run pytest -q tests/unit/test_catalog_service.py
uv run pytest -q tests/unit/test_handlers_dict.py
```

再跑聚合回归：

```bash
uv run pytest -q \
  tests/unit/test_repositories.py \
  tests/unit/test_resource_service_multimodal.py \
  tests/unit/test_hybrid_search.py \
  tests/unit/test_catalog_service.py \
  tests/unit/test_handlers_dict.py
```

如果要进一步确认没有旁路影响，再跑：

```bash
uv run pytest -q tests/unit
```

### 7.5 完成标准

Task 5 完成后必须满足：
- 五个测试文件全部通过
- 没有因为 service/repository 抽取导致 handler 返回结构变化
- 没有因为 handler 瘦身导致 section 查询功能回归
- Phase 1 的改动范围仍然局限在边界收敛

---

## 8. 总实施顺序

建议严格按下面顺序做，不要交叉乱改：

1. Task 1: 先建 repository 基础设施并补齐单测
2. Task 2: `ResourceService` 切到 repository
3. Task 3: `RetrievalService` 切到 `ActiveIndexRepository`
4. Task 4: 抽 `CatalogQueryService`，最后再瘦 `ToolHandlers`
5. Task 5: 跑 Phase 1 回归并收口

原因：
- Task 4 会依赖前面 repository 读法稳定
- handler 薄壳化应该放在 service 抽取之后
- 回归测试必须放在最后统一确认

---

## 9. Phase 1 总完成标准

以下条件全部满足，Phase 1 才算完成：

- `src/rag_mcp/indexing/repositories.py` 已存在并被测试覆盖
- `ResourceService` 不再直接 `json.loads(...)` store 文件
- `RetrievalService` 不再直接读取 `active_index.json`
- 新增 `CatalogQueryService`
- `src/rag_mcp/transport/handlers.py` 不再承载文档分组和 section 查询核心逻辑
- MCP tool 的返回结构与错误 dict 结构未发生破坏性变化
- Phase 1 相关 unit tests 全部通过

---

## 10. 本轮建议的提交切分

为了让 review 更清晰，建议至少拆成 4 个提交：

1. `feat: add repository layer for manifest and stores`
2. `refactor: migrate resource and retrieval services to repositories`
3. `refactor: extract catalog query service from tool handlers`
4. `test: add phase1 boundary regression coverage`

如果必须压缩，也至少拆成：
- 基础设施 + service 切换
- catalog 抽取 + handler 瘦身 + 测试

