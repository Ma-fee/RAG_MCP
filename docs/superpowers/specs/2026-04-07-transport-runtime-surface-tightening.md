# Spec: Transport / Runtime Surface 收口

**日期**: 2026-04-07
**范围**: `phase4-runtime-merge` 中 transport/runtime 最外层入口，以及 indexing / retrieval 中残余的外层宽泛类型

---

## 1. 背景

当前 `rag_mcp` 已经完成三轮核心收口：

- 依赖注入型 `Any` 已收紧为 `Protocol`
- `retrieval` / `resources` / `catalog` 的稳定成功返回已收紧为 `TypedDict`
- indexing schema layer 已建立共享 `TypedDict`

但这些类型边界还没有完整贯通到最外层 surface。当前仍有几类残余问题：

- `transport/mcp_server.py` 中 tool 和 resource 返回仍是裸 `dict`
- `transport/fastapi_app.py` 中 `resource_service` 仍是 `Any`
- `retrieval/reranker.py` 的 factory 返回仍是 `Any | None`
- `indexing/rebuild.py` 的外层返回仍是 `dict[str, Any]`
- `indexing/services.py` 的 rebuild 成功返回仍是宽泛 dict
- `SectionsMappingRepository.load()` 仍是宽泛返回

这会导致前面已经收紧的类型在“最后一层入口”重新退化，形成半途而废的边界。

---

## 2. 目标与非目标

### 目标

- 将 transport / runtime 最外层入口的成功返回注解收紧到明确类型
- 去掉 `fastapi_app` / `reranker factory` 里的残余 `Any`
- 为 rebuild 成功返回建立明确 response 类型
- 为 sections mapping repository 建立明确返回类型
- 保持实际外部行为和 JSON 字段不变

### 非目标

- 不修改错误返回结构
- 不修改 FastMCP / FastAPI 的行为路径
- 不重构 parser / chunker / docling 边界
- 不继续扩展 indexing 深层内部 helper 的 schema

---

## 3. 设计方案

### 3.1 MCP server 透传已有 success 类型

`mcp_server.py` 不应再把 `ToolHandlers` 的明确返回类型抹平成裸 `dict`。

做法：

- 为 `rag_search`、`rag_read_resource`、`rag_list_filenames`、`rag_list_sections`、`rag_section_retrieval`、`rag_resource` 使用与 `ToolHandlers` 一致的成功返回联合类型
- `rag_rebuild_index` 和 `rag_index_status` 若仍缺明确类型，则本轮先补上对应 response type

### 3.2 FastAPI app 依赖显式化

`create_app(resource_service: Any, ...)` 改为依赖一个明确可读接口。

优先做法：

- 新增最小 `Protocol`，例如 `ReadableResourceService`
- 或直接复用 `ResourceService`，若不会引入不必要耦合

鉴于 `fastapi_app` 只依赖 `read(uri)`，更推荐使用最小 `Protocol`。

### 3.3 Reranker factory 返回协议类型

`build_reranker(cfg) -> Any | None` 改为返回 `RerankerLike | None`。

这与前面 runtime DI 收口保持一致，也能让 bootstrap / config 路径避免回退到 `Any`。

### 3.4 Rebuild 成功返回类型化

为 rebuild 成功返回新增明确响应类型，例如：

- `RebuildIndexResponseDict`

至少包含：

- `corpus_id`
- `index_dir`
- `indexed_at`
- `document_count`
- `chunk_count`
- `embedding_model`
- `embedding_dimension`

并用于：

- `RebuildIndexService.rebuild_keyword_index()`
- `indexing.rebuild.rebuild_keyword_index()`
- `ToolHandlers.rebuild_index()` 相关中间结果

若 `ToolHandlers.rebuild_index()` 对外做了字段裁剪，则允许 handler 侧再定义一个更窄的成功返回类型，但 service / rebuild 函数不应继续返回宽泛 dict。

### 3.5 Sections mapping 返回类型化

`SectionsMappingRepository.load()` 改为：

- `dict[str, list[str]]`

或专门命名的 `TypedDict` / type alias，视具体需要而定。

由于该结构已经非常简单，本轮不必过度设计，直接明确返回 `dict[str, list[str]]` 即可。

---

## 4. 涉及文件

- `src/rag_mcp/transport/mcp_server.py`
- `src/rag_mcp/transport/fastapi_app.py`
- `src/rag_mcp/retrieval/reranker.py`
- `src/rag_mcp/indexing/rebuild.py`
- `src/rag_mcp/indexing/services.py`
- `src/rag_mcp/indexing/repositories.py`

必要时同步：

- `src/rag_mcp/runtime_types.py`
- `src/rag_mcp/transport/handlers.py`
- 相关 unit tests

---

## 5. 测试策略

遵循 TDD。

至少补这些测试：

- `mcp_server` 中 tool/resource 返回注解不再是裸 `dict`
- `fastapi_app.create_app()` 的 `resource_service` 参数不再是 `Any`
- `build_reranker()` 返回注解为 `RerankerLike | None`
- `rebuild_keyword_index()` / `RebuildIndexService.rebuild_keyword_index()` 的返回注解为明确 response 类型
- `SectionsMappingRepository.load()` 返回注解收紧

现有行为测试继续通过，证明收口不改行为。

---

## 6. 完成标准

- transport/runtime 最外层入口不再无条件退化成裸 `dict`
- `fastapi_app` / `reranker factory` 不再使用注入型 `Any`
- rebuild 成功返回拥有明确类型
- sections mapping repository 返回拥有明确类型
- 关键单测与集成测试保持通过
