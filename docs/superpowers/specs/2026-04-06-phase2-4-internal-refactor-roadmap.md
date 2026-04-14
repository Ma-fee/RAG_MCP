# Spec: `rag_mcp` 内部重构 Phase 2-4 路线图

**日期**: 2026-04-06
**范围**: 仅覆盖 `rag_mcp` 内部重构，不覆盖 `iroot-llm/xeno-agent`、`mcp-scratchpad`、跨项目 URI 联动协议

---

## 1. 背景

`rag_mcp` 已经完成了历史上的 v1 交付 phase：
- [phase-1-keyword-stdio-mvp.md](/Users/admin/Downloads/rag_mcp/plan/phase-1-keyword-stdio-mvp.md)
- [phase-2-vector-chroma.md](/Users/admin/Downloads/rag_mcp/plan/phase-2-vector-chroma.md)
- [phase-3-docling-structure.md](/Users/admin/Downloads/rag_mcp/plan/phase-3-docling-structure.md)
- [phase-4-http-parity-release.md](/Users/admin/Downloads/rag_mcp/plan/phase-4-http-parity-release.md)

在功能可用之后，当前开始进入“内部收口”阶段。

本轮新的重构 Phase 1 已经定义为：
- [2026-04-06-phase1-service-boundary-cleanup.md](/Users/admin/Downloads/rag_mcp/docs/superpowers/specs/2026-04-06-phase1-service-boundary-cleanup.md)

该 Phase 1 的定位是：
- 先把 repository / service / handler 的边界收紧
- 不修改 URI 契约
- 不系统性改 tool contract
- 不做大规模 config / app assembly 重写

因此，Phase 1 之后仍然会留下三类问题：
- 对外 tool contract 和 error model 仍有历史不一致
- service 之间的领域边界虽然变清楚了一些，但还没有形成稳定的 domain structure
- 运行时装配、config、transport wiring 仍然比较散

这就是后续 Phase 2 / 3 / 4 要解决的内容。

---

## 2. 总体目标

后续三期重构按下面顺序推进：

1. **Phase 2: Tool Contract / Error Model / Schema 收敛**
2. **Phase 3: Domain Service / Repository / Query-Write 边界重组**
3. **Phase 4: Config / Bootstrap / Transport Assembly 收口**

这三期的核心原则：
- 先固定“对外 contract”，再调整内部结构
- 先清晰 domain boundary，再整理 runtime assembly
- 每个 Phase 只解决一个主问题，避免一次重构所有层

---

## 3. 统一设计原则

### 3.1 契约先于实现

后续所有内部重构都必须服从稳定 tool contract。  
不能出现“内部改舒服了，但返回结构又变了”的情况。

### 3.2 Domain service 不关心 transport

service 层最终只应该：
- 接受标准 Python 参数
- 返回稳定 Python payload
- 通过 `ServiceException` 抛业务错误

service 不应该知道：
- MCP tool name
- FastMCP 注册方式
- stdio / sse / streamable-http 区别

### 3.3 Transport adapter 不写业务逻辑

handler / mcp server / fastapi app 这一层最终只应该做：
- 参数适配
- 调 service
- 异常翻译
- 输出格式适配

### 3.4 Config 只描述运行时，不承载领域逻辑

`AppConfig` 最终应该只是：
- 环境变量解析
- 默认值
- provider 选择
- runtime wiring 所需配置

不能让 config 模块开始承担业务规则或 handler 决策。

### 3.5 Query path 与 write path 分离

后续重构中，必须更明确区分：
- 写路径：ingestion / rebuild / persist / manifest update
- 读路径：catalog / retrieval / resources / query services

这对后面引入 cache、multi-index、snapshot、只读模式都很关键。

---

## 4. Phase 2: Tool Contract / Error Model / Schema 收敛

### 4.1 Phase 目标

在 Phase 1 收紧 service boundary 之后，Phase 2 的目标是把所有 MCP tool 的输入输出 contract 收成一套可维护规则。

这个 Phase 优先解决：
- error dict 字面值不统一
- handler 返回 payload 风格不统一
- tool 之间成功返回结构风格不统一
- service error 与 transport error 之间映射关系不稳定

### 4.2 Phase 非目标

- 不重做 indexing pipeline
- 不改 `rag://` URI 契约
- 不重写 `main.py`
- 不重做 FastMCP server 框架
- 不引入跨项目联动协议

### 4.3 Phase 产物

完成后至少应有：
- 一套统一的 tool output schema 规则
- 一套统一的 error translation 规则
- handler 层公共的 success / error 输出 helper
- 稳定的 tool-level 回归测试
- 文档中明确哪些字段属于“外部 contract”

### 4.4 Task 2.1: 定义统一错误模型边界

#### 目标

明确：
- repository error
- service error
- transport error

这三层之间的职责和转换规则。

#### 涉及文件

- 修改: `src/rag_mcp/errors.py`
- 修改: `src/rag_mcp/transport/handlers.py`
- 新增测试: `tests/unit/test_error_contract.py`

#### 具体改法

当前 `ErrorCode` 还比较少，且部分 handler 仍会直接返回：

```python
{"error": "invalid_filename", "message": "..."}
```

Phase 2 需要明确：

1. `ErrorCode` 继续作为 service 层唯一正式错误码来源
2. handler 层不再随意发明新的 error 字面值
3. handler 统一把 `ServiceException` 映射成：

```python
{
    "error": exc.error.code.value,
    "message": exc.error.message,
}
```

必要时再增加可选字段：

```python
{
    "error": exc.error.code.value,
    "message": exc.error.message,
    "hint": exc.error.hint,
    "details": exc.error.details,
}
```

但是否默认暴露 `hint` / `details`，必须在 Phase 2 内一次定清，不允许 tool 之间各自发挥。

建议在 `errors.py` 中扩出一组更完整的业务错误码，例如：

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

#### 行为规范

| 场景 | 期望 |
|------|------|
| 参数缺失 | 统一收敛到 `INVALID_ARGUMENT` |
| 文档不存在 | `RESOURCE_NOT_FOUND` |
| 无活动索引 | `NO_ACTIVE_INDEX` |
| rebuild 失败 | `REBUILD_FAILED` |
| 未知内部异常 | `INTERNAL_ERROR` |

#### 先写的测试

`tests/unit/test_error_contract.py` 至少覆盖：
- `ServiceException` -> handler dict 的标准映射
- 非 `ServiceException` 的兜底错误映射
- 参数错误是否统一为 `INVALID_ARGUMENT`

#### 完成标准

- handler 不再输出历史散装 error literal
- `ErrorCode` 成为唯一正式业务错误码集合
- 新增错误 contract 测试

### 4.5 Task 2.2: 统一 ToolHandlers 成功返回 schema 风格

#### 目标

把现有工具返回结构统一成少数几种模式，而不是每个工具都各写一套。

#### 涉及文件

- 修改: `src/rag_mcp/transport/handlers.py`
- 可能新增: `src/rag_mcp/transport/presenters.py`
- 修改测试: `tests/unit/test_handlers_dict.py`
- 新增测试: `tests/unit/test_tool_output_contract.py`

#### 具体改法

建议把成功返回分成四类：

1. **单对象型**

```python
{
    ...
}
```

适用于：
- `index_status`
- `read_resource`

2. **列表型**

```python
{
    "count": n,
    "results": [...],
}
```

适用于：
- `read_resources`

3. **查询结果型**

```python
{
    "query": "...",
    "result_count": n,
    "results": [...],
}
```

适用于：
- `search`
- `section_retrieval`

4. **目录/枚举型**

```python
{
    "count": n,
    "items": [...],
}
```

适用于：
- `list_filenames`

如果不想在 Phase 2 里直接把 `filenames` 改成 `items`，那就至少要在文档中明确：
- `filenames` 是稳定 contract
- 后续不要再继续出现 `documents`、`files`、`items` 多种别名

建议这一步先新增 presenter/helper，例如：

```python
def success_list(*, items: list[dict[str, Any]], key: str = "results") -> dict[str, Any]:
    return {"count": len(items), key: items}


def success_query(
    *,
    query: str,
    results: list[dict[str, Any]],
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {"query": query, "result_count": len(results), "results": results}
    if extra:
        payload.update(extra)
    return payload
```

#### 行为规范

Phase 2 必须在文档中把下列返回结构固定：
- `rebuild_index`
- `index_status`
- `search`
- `read_resource`
- `read_resources`
- `list_filenames`
- `list_sections`
- `section_retrieval`

#### 先写的测试

`tests/unit/test_tool_output_contract.py` 至少覆盖：
- `search` 返回字段稳定
- `read_resources` 的 `count/success_count/error_count/results` 稳定
- `list_filenames` 的键名稳定
- `section_retrieval` 的 `requested_section_titles/result_count/results` 稳定

#### 完成标准

- 所有 tool 成功返回结构在文档中被明确定义
- handler 中不再散落重复的 payload 拼装逻辑
- presenter/helper 如果被引入，至少覆盖一个通用单测文件

### 4.6 Task 2.3: 统一参数校验和输入规范化

#### 目标

把现在散在 handler 里的参数校验逻辑统一起来，避免每个方法都自己判断空字符串、空列表、strip 等。

#### 涉及文件

- 修改: `src/rag_mcp/transport/handlers.py`
- 可能新增: `src/rag_mcp/transport/validation.py`
- 新增测试: `tests/unit/test_transport_validation.py`

#### 具体改法

建议抽出最小的 validation helper：

```python
def require_non_empty_string(value: str, *, field: str) -> str: ...
def require_non_empty_string_list(values: list[str], *, field: str) -> list[str]: ...
def normalize_top_k(value: int | None, *, default: int, minimum: int = 1) -> int: ...
```

handler 中原本这种代码：

```python
if not filename or not filename.strip():
    return {"error": "...", "message": "..."}
```

改成统一路径：

```python
try:
    normalized_filename = require_non_empty_string(filename, field="filename")
except ServiceException as exc:
    return self._service_error_dict(exc)
```

#### 行为规范

| 参数类型 | 规范 |
|---------|------|
| `filename` | 非空字符串，自动 strip |
| `query` | 非空字符串，自动 strip |
| `section_title` | 非空字符串数组，逐项 strip |
| `top_k` | 非空时必须 >= 1 |
| `directory_path` | 非空字符串，保持原始路径用于展示 |

#### 先写的测试

`tests/unit/test_transport_validation.py` 至少覆盖：
- 空字符串报 `INVALID_ARGUMENT`
- 全空白字符串报 `INVALID_ARGUMENT`
- `section_title=["", "  "]` 报 `INVALID_ARGUMENT`
- `top_k=0` 报 `INVALID_ARGUMENT`

#### 完成标准

- handler 参数校验逻辑统一收口
- 业务错误码不再混入“字段名专属 error literal”

### 4.7 Task 2.4: 固化 tool contract 文档与回归测试

#### 目标

把前面三个 task 的结果固化到文档和测试中，避免以后又被改散。

#### 涉及文件

- 修改: `README.md`
- 可新增: `docs/tool-contract.md`
- 修改测试: `tests/unit/test_handlers_dict.py`
- 可新增集成测试: `tests/integration/test_tool_contract_stability.py`

#### 具体改法

文档中要明确：
- 每个 tool 的参数
- 每个 tool 的成功返回结构
- 每个 tool 的错误返回结构
- 哪些字段是稳定 contract

如果要单独出文档，建议结构如下：

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

#### 完成标准

- tool contract 以文档形式固定
- unit/integration 两层至少有一层覆盖 contract 稳定性

### 4.8 Phase 2 验收命令

```bash
uv run pytest -q \
  tests/unit/test_error_contract.py \
  tests/unit/test_tool_output_contract.py \
  tests/unit/test_transport_validation.py \
  tests/unit/test_handlers_dict.py
```

### 4.9 Phase 2 完成标准

- `ErrorCode` 成为正式统一错误码集合
- handler 不再发明零散 error literal
- tool success/error contract 被文档化
- 参数校验路径统一
- Phase 2 相关测试通过

---

## 5. Phase 3: Domain Service / Repository / Query-Write 边界重组

### 5.1 Phase 目标

在 Phase 2 固定对外 contract 之后，Phase 3 的目标是把内部领域结构真正理顺。

重点不是再改 handler，而是让下面四个领域更清楚：
- `catalog`
- `resources`
- `retrieval`
- `indexing`

### 5.2 Phase 非目标

- 不改对外 tool contract
- 不改 transport 类型
- 不引入新业务功能
- 不处理跨项目 URI

### 5.3 Phase 产物

完成后至少应有：
- 清晰的 query services
- 清晰的 write-side indexing services
- repository 只做数据访问
- service 只做业务逻辑
- query path 与 write path 分离

### 5.4 Task 3.1: 收口 indexing 写路径

#### 目标

把 `indexing/rebuild.py` 里“流程编排”和“具体持久化细节”进一步分离，为 Phase 4 的 runtime assembly 做准备。

#### 涉及文件

- 修改: `src/rag_mcp/indexing/rebuild.py`
- 可能新增:
  - `src/rag_mcp/indexing/services.py`
  - `src/rag_mcp/indexing/persistence.py`
- 测试:
  - `tests/unit/test_rebuild_multimodal.py`
  - `tests/unit/test_indexing_services.py`

#### 具体改法

建议把 `rebuild_keyword_index(...)` 分成三层：

1. orchestration
2. domain transformation
3. persistence

例如：

```python
class RebuildIndexService:
    def rebuild(self, source_dir: Path) -> dict[str, Any]: ...


class IndexPersistenceService:
    def write_manifest(self, manifest: dict[str, Any]) -> None: ...
    def write_keyword_store(self, payload: dict[str, Any]) -> None: ...
    def write_resource_store(self, payload: dict[str, Any]) -> None: ...
    def write_sections_mapping(self, payload: dict[str, list[str]]) -> None: ...
```

当前 Phase 不要求一定改成 class，但要求职责拆开，不再让一个大函数同时做：
- ingestion
- chunking
- embedding
- resource linking
- store persistence
- manifest 更新

#### 完成标准

- `rebuild.py` 不再是单个超大 orchestration 脚本
- 持久化写入职责有单独边界
- rebuild 回归测试通过

### 5.5 Task 3.2: 固定 query-side service 分层

#### 目标

把 Phase 1 引入的 service boundary 做成稳定的 query-side 架构，而不是“先拆出来但继续演化不清”。

#### 涉及文件

- 修改/新增:
  - `src/rag_mcp/catalog/service.py`
  - `src/rag_mcp/resources/service.py`
  - `src/rag_mcp/retrieval/service.py`
  - `src/rag_mcp/indexing/repositories.py`
- 可新增:
  - `src/rag_mcp/catalog/repositories.py`
  - `src/rag_mcp/retrieval/models.py`

#### 具体改法

目标结构建议为：

```text
repositories/
  active index
  keyword store
  resource store
  sections mapping

query services/
  CatalogQueryService
  ResourceService
  RetrievalService

transport/
  ToolHandlers
```

并明确每个服务的唯一职责：

- `CatalogQueryService`
  - 文档目录浏览
  - 章节列表
  - section retrieval

- `ResourceService`
  - `rag://` 读取
  - resource payload enrich

- `RetrievalService`
  - keyword/vector/hybrid 查询编排
  - query splitting
  - rerank

这一步不要求把所有公共逻辑抽成“基类”，更不建议为了抽象而抽象。  
重点是职责不交叉。

#### 先写的测试

至少确认：
- `CatalogQueryService` 不直接参与 transport dict 输出
- `RetrievalService` 不读取 transport 配置
- `ResourceService` 不知道 tool name

可以通过小型架构单测或模块依赖断言实现。

#### 完成标准

- query-side 三个 service 职责边界稳定
- handler 只做 adapter
- repository 不承担业务逻辑

### 5.6 Task 3.3: 引入内部 payload model，但不强制暴露给 MCP

#### 目标

在不破坏外部 dict contract 的前提下，引入内部数据模型，降低 service 之间传裸 dict 的风险。

#### 涉及文件

- 可新增:
  - `src/rag_mcp/catalog/models.py`
  - `src/rag_mcp/retrieval/models.py`
  - `src/rag_mcp/resources/models.py`
- 修改对应 service
- 测试: `tests/unit/test_internal_models.py`

#### 具体改法

这一步可以开始考虑你前面提过的“更像 scratchpad 的代码风格”，但建议只用于**内部 model**，不要直接把外部 contract 一口气改成 Pydantic API layer。

建议两种可接受方式：

1. `dataclass`
2. `pydantic.BaseModel`

推荐：
- Phase 3 内部先用 `dataclass` 或轻量 Pydantic model 管理 service 内部 payload
- handler 仍然在最外层输出 dict

例如：

```python
@dataclass(frozen=True)
class SearchHit:
    uri: str
    text: str
    title: str
    score: float
    metadata: dict[str, Any]
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
```

这一步的重点是：
- service 内部不再层层裸 dict
- transport 仍保持现有 contract

#### 完成标准

- 关键 query payload 有内部模型
- service 内部 dict 传递显著减少
- 不影响 Phase 2 固定的外部 contract

### 5.7 Task 3.4: 固化 query / write 路径边界

#### 目标

从结构上明确：
- rebuild/indexing 是 write path
- retrieval/catalog/resources 是 read path

避免后续继续在 query service 里混入写逻辑或在 rebuild 流程里混入 query helper。

#### 涉及文件

- 可能新增目录:
  - `src/rag_mcp/query/`
  - `src/rag_mcp/indexing/services/`
- 或者只在现有目录内通过命名和文档固定
- 可新增文档:
  - `docs/architecture/query-write-boundary.md`

#### 具体改法

这一步不一定要求物理搬目录，但至少要形成清晰规则：

- 读路径模块不写 manifest/store
- 写路径模块不做 tool result formatting
- query service 只读 active index
- rebuild service 负责生成新 index 并切 active manifest

如果要做结构化命名，建议：

```text
rag_mcp/indexing/...     # write-side
rag_mcp/catalog/...      # read-side browse/query
rag_mcp/retrieval/...    # read-side search
rag_mcp/resources/...    # read-side resource fetch
rag_mcp/transport/...    # adapter
```

#### 完成标准

- query/write 责任边界写入文档
- 代码结构与文档不冲突
- 不再出现明显交叉职责

### 5.8 Phase 3 验收命令

```bash
uv run pytest -q \
  tests/unit/test_catalog_service.py \
  tests/unit/test_resource_service_multimodal.py \
  tests/unit/test_hybrid_search.py \
  tests/unit/test_rebuild_multimodal.py
```

如引入内部模型与 indexing service，再补：

```bash
uv run pytest -q \
  tests/unit/test_internal_models.py \
  tests/unit/test_indexing_services.py
```

### 5.9 Phase 3 完成标准

- write-side indexing 边界更清楚
- read-side query services 职责更清楚
- 内部 payload model 初步建立
- query/write 路径边界有文档和测试支撑

---

## 6. Phase 4: Config / Bootstrap / Transport Assembly 收口

### 6.1 Phase 目标

在 contract 和 domain structure 都稳定之后，Phase 4 负责整理运行时装配。

重点解决：
- `main.py` 里装配逻辑堆积
- `AppConfig` 只是一大坨 env parser，缺少 provider/runtime 分层
- transport 创建、handler 创建、provider 创建耦合在入口文件
- 测试与运行时装配路径不完全一致

### 6.2 Phase 非目标

- 不新增业务能力
- 不改外部 tool contract
- 不改 `rag://` 规则
- 不重做 domain service 行为

### 6.3 Phase 产物

完成后至少应有：
- 明确的 bootstrap / container 入口
- config 分层
- provider factory 收口
- transport 装配统一
- 更易测试的 app assembly

### 6.4 Task 4.1: 拆分 `AppConfig` 为 runtime / provider / retrieval 配置

#### 目标

把当前单一 `AppConfig` 拆成更清晰的 config 结构。

#### 涉及文件

- 修改: `src/rag_mcp/config.py`
- 修改: `main.py`
- 新增测试: `tests/unit/test_config_models.py`

#### 具体改法

当前 `AppConfig` 同时承载：
- data dir
- http host/port
- embedding provider
- multimodal provider
- rerank provider
- retrieval tuning

建议拆成：

```python
@dataclass(frozen=True)
class RuntimeConfig:
    data_dir: Path
    mcp_transport: str
    http_host: str
    http_port: int


@dataclass(frozen=True)
class EmbeddingConfig:
    api_key: str
    base_url: str
    model: str
    dimension: int | None
    timeout_seconds: int


@dataclass(frozen=True)
class RerankConfig:
    api_key: str
    base_url: str
    model: str
    timeout_seconds: int
    top_k_candidates: int


@dataclass(frozen=True)
class IngestionConfig:
    multimodal_api_key: str
    multimodal_base_url: str
    multimodal_model: str
    chunk_size: int
    chunk_overlap: int


@dataclass(frozen=True)
class AppConfig:
    runtime: RuntimeConfig
    embedding: EmbeddingConfig
    rerank: RerankConfig
    ingestion: IngestionConfig
    default_top_k: int
    keyword_top_k: int
```

#### 完成标准

- config 语义按职责分组
- `main.py` 不再直接依赖一大串平铺字段
- config 单测覆盖 env parsing

### 6.5 Task 4.2: 抽出 bootstrap / factory 层

#### 目标

把现在 `main.py` 里的 provider 初始化和 handler 初始化搬到单独 bootstrap/factory 模块。

#### 涉及文件

- 新增:
  - `src/rag_mcp/bootstrap.py`
  - 或 `src/rag_mcp/app_factory.py`
- 修改:
  - `main.py`
- 测试:
  - `tests/unit/test_bootstrap.py`

#### 具体改法

当前 `main.py` 直接做：
- `AppConfig.from_env()`
- `EmbeddingClient.from_config(cfg)`
- `VlmClient.from_config(cfg)`
- `build_reranker(cfg)`
- `ToolHandlers(...)`
- `create_mcp_server(handlers)`

建议改为：

```python
@dataclass(frozen=True)
class Application:
    config: AppConfig
    handlers: ToolHandlers
    mcp_server: Any


def build_application() -> Application: ...
def build_handlers(cfg: AppConfig) -> ToolHandlers: ...
def build_embedding_provider(cfg: AppConfig) -> Any | None: ...
def build_vlm_client(cfg: AppConfig) -> Any | None: ...
def build_mcp_server(handlers: ToolHandlers) -> Any: ...
```

然后 `main.py` 退化成：

```python
def main() -> None:
    app = build_application()
    run_application(app)
```

#### 完成标准

- `main.py` 变成薄入口
- provider / handler / server 的创建有独立 factory
- bootstrap 逻辑可单测

### 6.6 Task 4.3: 统一 transport 装配入口

#### 目标

让 stdio / sse / streamable-http 共用同一套应用装配，而不是入口层分别处理。

#### 涉及文件

- 修改:
  - `main.py`
  - `src/rag_mcp/transport/mcp_server.py`
  - `src/rag_mcp/transport/fastapi_app.py`
- 可新增:
  - `src/rag_mcp/transport/runtime.py`
- 测试:
  - `tests/integration/test_phase4_http_stdio_parity.py`
  - 可新增 `tests/unit/test_transport_runtime.py`

#### 具体改法

建议抽一个 runtime runner：

```python
def run_application(app: Application) -> None:
    transport = app.config.runtime.mcp_transport
    if transport == "stdio":
        app.mcp_server.run(transport="stdio")
    elif transport == "sse":
        app.mcp_server.run(
            transport="sse",
            host=app.config.runtime.http_host,
            port=app.config.runtime.http_port,
        )
    elif transport in {"streamable-http", "streamable_http"}:
        app.mcp_server.run(
            transport="streamable-http",
            host=app.config.runtime.http_host,
            port=app.config.runtime.http_port,
        )
    else:
        raise ValueError(f"unsupported MCP transport: {transport}")
```

这样 Phase 4 完成后，transport 只是 runtime 选择，不再影响 service/handler 初始化路径。

#### 完成标准

- stdio/http transport 共用同一套 application wiring
- 传输层差异只体现在 runtime runner
- parity 测试继续通过

### 6.7 Task 4.4: 建立测试装配与运行时装配一致性

#### 目标

让单元测试、集成测试、真实运行尽量共用同一套 build path，减少“生产代码从 A 入口跑，测试从 B 入口拼”的偏差。

#### 涉及文件

- 修改测试基建
- 可新增:
  - `tests/helpers/app_factory.py`
  - `tests/conftest.py`
- 修改:
  - `tests/integration/test_phase1_stdio_keyword_flow.py`
  - `tests/integration/test_phase2_vector_keyword_parity.py`
  - `tests/integration/test_phase4_http_stdio_parity.py`

#### 具体改法

目标不是让测试去调用 `main()`，而是让测试尽量复用：
- `build_application()`
- `build_handlers()`
- `run_application()` 或 transport-specific runner

这样能确保：
- 测试环境和生产环境的 handler/service/provider wiring 一致
- 入口层变更更容易被测试捕获

#### 完成标准

- 测试对 runtime wiring 的覆盖增强
- build path 更少分叉

### 6.8 Phase 4 验收命令

```bash
uv run pytest -q \
  tests/unit/test_config_models.py \
  tests/unit/test_bootstrap.py \
  tests/integration/test_phase4_http_stdio_parity.py
```

如测试装配被统一，再补：

```bash
uv run pytest -q \
  tests/integration/test_phase1_stdio_keyword_flow.py \
  tests/integration/test_phase2_vector_keyword_parity.py \
  tests/integration/test_phase4_http_stdio_parity.py
```

### 6.9 Phase 4 完成标准

- config 结构清晰分层
- `main.py` 成为薄入口
- bootstrap / factory 独立存在
- stdio/http 共享同一套装配路径
- 测试装配与运行时装配更一致

---

## 7. 总实施顺序

严格建议按以下顺序推进：

1. 先完成 Phase 1 的 service boundary cleanup
2. 再做 Phase 2 的 tool contract / error model 收敛
3. 再做 Phase 3 的 domain service / repository / query-write 边界重组
4. 最后做 Phase 4 的 config / bootstrap / transport assembly 收口

原因：
- 如果 contract 还没固定就去重组 domain service，后面 handler 很容易返工
- 如果 domain 还不稳定就先抽 bootstrap/container，装配层会把不稳定结构固化下来

---

## 8. 后续计划文档建议

这份文档是路线图 spec，不是 implementation plan。  
后续应该按每个 Phase 再分别写一份 plan。

建议后续新增：
- `docs/superpowers/specs/2026-04-06-phase2-tool-contract-unification.md`
- `docs/superpowers/specs/2026-04-06-phase3-domain-boundary-restructure.md`
- `docs/superpowers/specs/2026-04-06-phase4-runtime-assembly-cleanup.md`

如要进入执行，再分别产出：
- `docs/superpowers/plans/YYYY-MM-DD-phase2-...md`
- `docs/superpowers/plans/YYYY-MM-DD-phase3-...md`
- `docs/superpowers/plans/YYYY-MM-DD-phase4-...md`

---

## 9. 总完成标准

当 Phase 2-4 全部完成后，`rag_mcp` 应达到以下状态：

- 对外 tool contract 稳定
- 错误模型统一
- handler 不承载领域逻辑
- repository / service / transport 分层清晰
- query path / write path 明确分离
- config / bootstrap / transport assembly 有稳定结构
- 测试对 contract、domain、runtime assembly 三层都有覆盖

---

## 10. 风险与控制点

### 风险 1: 一边改 contract 一边改 domain，导致回归面过大

控制方式：
- Phase 2 只动 contract，不大改 indexing/domain 结构

### 风险 2: 过早全面引入 Pydantic，导致 API layer 和内部 model 一起震荡

控制方式：
- Phase 3 只把内部 payload model 化
- 外部 MCP contract 仍保持 dict 输出

### 风险 3: 先做 bootstrap/container，结果把不稳定 service 边界固化

控制方式：
- bootstrap 收口放到 Phase 4 最后做

### 风险 4: 文档和代码演化不同步

控制方式：
- 每个 Phase 完成后都更新该 Phase spec 与测试
- 不允许跨 Phase 偷做下一期工作

