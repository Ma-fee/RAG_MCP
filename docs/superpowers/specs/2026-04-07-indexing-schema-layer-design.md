# Spec: Indexing Schema Layer 收口

**日期**: 2026-04-07
**范围**: `phase4-runtime-merge` 中 indexing 路径的稳定数据结构，包括 manifest、keyword entry、resource entry、vector entry / hit，以及对应 repository / persistence / service / index adapter 的类型边界

---

## 1. 背景

当前 `rag_mcp` 已经完成了两轮高价值收口：

- 运行时依赖注入型 `Any` 已收紧为 `Protocol`
- `retrieval` / `resources` / `catalog` 的稳定成功返回结构已收紧为 `TypedDict`

剩余最值得优先处理的宽泛类型，集中在 indexing 路径的内部数据图：

- `active_index.json` manifest
- `keyword_store.json` 的 entries
- `resource_store.json` 的 entries
- vector upsert / vector hit payload
- repository / persistence / index adapter 之间的中间 dict

这些结构虽然是“内部数据”，但它们并不是任意 JSON，而是已经稳定的核心 schema。继续维持 `dict[str, Any]` / `list[Any]` 会导致：

- repository / service 边界依然含糊
- `keyword_index` / `vector_index` / `persistence` 的接口缺少稳定契约
- 一旦字段变更，很难被静态检查和测试第一时间发现

---

## 2. 目标与非目标

### 目标

- 为 indexing 内部稳定结构建立共享 `TypedDict`
- 收紧 repository / persistence / service / index adapter 的参数和返回类型
- 明确区分：
  - manifest schema
  - keyword entry schema
  - resource entry schema
  - vector entry schema
  - vector hit schema
- 不改变现有 JSON 文件字段

### 非目标

- 不改外部 MCP tool contract
- 不重构 docling / parser 的第三方对象边界
- 不处理 `ingestion/document_model.py` 中 `metadata` 的开放结构
- 不改 experiment 路径的主流程地位
- 不重做 Chroma 持久化格式

---

## 3. 设计方案

新增一个共享 indexing schema 模块，集中定义稳定数据结构。

建议新文件：

- `src/rag_mcp/indexing/types.py`

建议类型至少包含：

- `ActiveManifestDict`
- `KeywordEntryMetadataDict`
- `KeywordEntryDict`
- `ResourceEntryDict`
- `VectorChunkEntryDict`
- `VectorSearchHitDict`
- `KeywordStorePayloadDict`
- `ResourceStorePayloadDict`

设计原则：

1. **共享 schema 放在单一模块**
   避免 `repositories.py`、`services.py`、`keyword_index.py`、`vector_index.py` 各自定义同义结构。

2. **先表达稳定外层，再接受局部宽泛字段**
   例如 `metadata` 内部若仍有少量开放字段，可以先用更宽泛的子字段类型，但外层结构和关键字段必须固定。

3. **JSON 持久化格式不变**
   本轮只收紧类型，不调整 `keyword_store.json` / `resource_store.json` / `active_index.json` 的字段。

4. **Repository 返回具体 payload 类型**
   `KeywordStoreRepository.entries()` 不应再返回 `list[Any]`，而应返回 `list[KeywordEntryDict]`。

5. **Index adapter 输入输出具体化**
   `KeywordIndex.search()`、`VectorIndex.upsert_chunks()`、`VectorIndex.search_by_vector()` 应使用明确 entry / hit 类型。

---

## 4. 涉及模块

### 4.1 Schema 定义

- 新增: `src/rag_mcp/indexing/types.py`

### 4.2 Repository / Manifest / Persistence

- `src/rag_mcp/indexing/repositories.py`
- `src/rag_mcp/indexing/manifest.py`
- `src/rag_mcp/indexing/persistence.py`

### 4.3 Service / Store / Index Adapter

- `src/rag_mcp/indexing/services.py`
- `src/rag_mcp/indexing/resource_store.py`
- `src/rag_mcp/indexing/keyword_index.py`
- `src/rag_mcp/indexing/vector_index.py`
- `src/rag_mcp/indexing/rebuild.py`

---

## 5. 分阶段收口策略

### 5.1 Phase A: Manifest / Repository Schema

先把：

- `ActiveIndexRepository`
- `KeywordStoreRepository`
- `ResourceStoreRepository`
- `SectionsMappingRepository`
- `read_active_manifest()`
- `write_active_manifest_atomic()`

的返回类型收成明确 schema。

这是最稳的一层，因为结构已经持久化在磁盘上，字段相对固定。

### 5.2 Phase B: Keyword / Resource Entry Schema

再把：

- `ResourceStore` 构建出来的条目
- `RebuildIndexService` 生成和消费的 keyword entries
- `KeywordIndex` 的 search hit

统一到共享 entry 类型上。

### 5.3 Phase C: Vector Entry / Hit Schema

最后把：

- `VectorIndex.upsert_chunks()` 的输入
- `VectorIndex.search_by_vector()` 的输出

收成明确类型。

---

## 6. 测试策略

遵循 TDD。

至少补以下测试：

- repository 返回注解和 payload 结构测试
- resource / keyword entry 构造结构测试
- vector upsert / search 的 payload 类型化回归
- 现有 indexing / retrieval 回归测试继续通过

建议新增或扩展：

- `tests/unit/test_repositories.py`
- `tests/unit/test_resource_store.py`
- `tests/unit/test_vector_index.py`
- `tests/unit/test_response_typing.py` 或新增 indexing typing 测试文件

---

## 7. 完成标准

- indexing 内部稳定 schema 有单一共享定义
- repository / manifest / persistence 的返回与入参不再使用 `list[Any]`
- keyword / resource / vector entry 的关键路径接口不再使用宽泛 dict
- JSON 持久化字段不变
- 现有关键 indexing / retrieval / integration 测试保持通过
