# Spec: 稳定成功返回结构类型收紧

**日期**: 2026-04-07
**范围**: `phase4-runtime-merge` 中 `retrieval`、`resources`、`catalog` 的稳定成功返回结构，以及对应 service / handler 的成功返回注解

---

## 1. 背景

上一轮已经把运行时依赖注入边界上的 `Any` 收紧为明确协议，但当前仍有另一类高价值、低风险的宽泛类型：

- `SearchHit.to_dict()` 返回 `dict[str, Any]`
- `TextResourcePayload.to_dict()` 返回 `dict[str, Any]`
- `SectionResult.to_dict()` 返回 `dict[str, Any]`
- 对应 service / handler 的成功返回值仍大量标成 `dict[str, Any]` 或裸 `dict`

这些结构并不是任意 JSON，而是已经稳定的对外成功返回 contract。继续保持宽泛返回会导致：

- 成功返回字段缺少显式类型文档
- service / handler 签名难以反映真实 contract
- IDE / 静态检查无法区分“稳定字段”和“任意 payload”

本轮目标是把这类稳定成功返回结构显式类型化，同时不改外部字段本身。

---

## 2. 目标与非目标

### 目标

- 保留现有 dataclass 模型
- 为稳定结果项增加 `TypedDict`
- 为对应成功响应体增加 `TypedDict`
- 将 `to_dict()`、service 成功返回、handler 成功返回注解收紧到明确类型
- 保持实际返回字段与当前行为完全一致

### 非目标

- 不修改错误返回结构
- 不统一 `ServiceException` / transport error contract
- 不改 `metadata` 内部 schema
- 不把所有 `dict[str, Any]` 一次性替换完
- 不改外部 MCP tool 名称或字段

---

## 3. 设计方案

采用“**保留 dataclass + 增补 TypedDict**”的方式，而不是把模型完全改成纯 `TypedDict`。

原因：

- dataclass 已经承担了内部结构表达与构造职责，直接删除会扩大改动面
- `TypedDict` 更适合表达稳定的 dict contract，尤其适合 `to_dict()` 和 service / handler 返回签名
- 两者并存可以最小侵入地提升类型精度

设计规则：

1. **结果项类型** 放在对应模型模块中
2. **响应体类型** 优先放在对应 service 模块中，靠近返回构造逻辑
3. `to_dict()` 返回结果项 `TypedDict`
4. service 成功返回值标注为对应响应体 `TypedDict`
5. handler 成功返回注解同步收紧到相同成功响应体或其联合类型

---

## 4. 范围与顺序

按以下顺序推进，逐层验证：

### 4.1 Retrieval

优先处理：

- `src/rag_mcp/retrieval/models.py`
- `src/rag_mcp/retrieval/service.py`
- `src/rag_mcp/transport/handlers.py`

建议类型：

- `SearchHitDict`
- `SearchResponseDict`

`SearchResponseDict` 至少应包含：

- `query`
- `mode`
- `top_k`
- `result_count`
- `results: list[SearchHitDict]`

### 4.2 Resources

优先处理：

- `src/rag_mcp/resources/models.py`
- `src/rag_mcp/resources/service.py`
- `src/rag_mcp/transport/handlers.py`

建议类型：

- `TextResourcePayloadDict`
- `ReadResourceResponseDict`

这里允许 `ReadResourceResponseDict` 暂时仍把 `metadata` 保持为宽泛字段，只要外层稳定结构明确。

### 4.3 Catalog

优先处理：

- `src/rag_mcp/catalog/models.py`
- `src/rag_mcp/catalog/service.py`
- `src/rag_mcp/transport/handlers.py`

建议类型：

- `SectionResultDict`
- `ListFilenamesResponseDict`
- `ListSectionsResponseDict`
- `SectionRetrievalResponseDict`

---

## 5. 外部 contract 约束

本轮只收紧类型表达，不改返回字段。

例如：

- `RetrievalService.search()` 仍返回包含 `query`、`mode`、`top_k`、`result_count`、`results` 的 dict
- `ResourceService.read()` 仍返回现有字段集合
- `CatalogQueryService` 相关接口仍返回当前 `count` / `filenames`、`section_count` / `sections`、`result_count` / `results` 结构

不允许因为“类型更明确”而调整字段名、字段层级、是否存在该字段。

---

## 6. 测试策略

遵循 TDD。

至少覆盖：

- `to_dict()` 返回类型对应的结构测试
- service 返回注解从宽泛 dict 收紧为明确响应类型
- handler 成功返回注解同步收紧
- 现有行为测试继续通过，证明 contract 未变

测试重点不是证明 `TypedDict` 在运行时强校验，而是证明代码结构已经对稳定成功返回建立明确类型边界。

---

## 7. 完成标准

- `retrieval` / `resources` / `catalog` 的稳定结果项拥有明确 `TypedDict`
- 对应 service 成功返回注解不再使用 `dict[str, Any]`
- 对应 handler 成功返回注解同步收紧
- 所有现有成功返回字段保持不变
- 错误返回结构保持不变
