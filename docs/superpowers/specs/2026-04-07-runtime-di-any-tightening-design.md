# Spec: `phase4-runtime-merge` 依赖注入型 `Any` 收紧

**日期**: 2026-04-07
**范围**: `phase4-runtime-merge` worktree 中运行时装配、service 依赖注入边界上的 `Any`

---

## 1. 背景

`phase4-runtime-merge` 已完成 Phase 4 的运行时装配收口，但当前仍有一批注入型依赖使用宽泛的 `Any`：

- `ToolHandlers` 的 `embedding_provider`、`vlm_client`、`reranker`
- rebuild / indexing service 的 provider/client 注入参数
- retrieval service 的 reranker 注入参数
- resource store 的 VLM client 注入参数

这些位置不是任意 JSON 载荷，而是明确的运行时协作对象。继续保留 `Any` 会带来几个问题：

- 调用方依赖的方法集合不明确
- stub / fake 的契约靠运行时碰撞，而不是静态检查
- 装配边界难以判断哪些参数已过时或未被使用

本次目标是把这类 `Any` 收紧为最小可用接口，同时不扩大到 payload schema 重构。

---

## 2. 目标与非目标

### 目标

- 去掉依赖注入边界上的 `Any`
- 用最小接口显式表达 provider/client/reranker 的协作契约
- 保持现有运行时 wiring 和外部 tool contract 不变
- 让测试替身可以基于显式接口工作

### 非目标

- 不处理 `dict[str, Any]`、`metadata: dict[str, Any]` 等数据载荷型 `Any`
- 不重写 JSON schema、repository payload、DTO/TypedDict
- 不修改 MCP tool 的输入输出 contract
- 不引入新的领域行为

---

## 3. 设计方案

采用 `typing.Protocol`，而不是直接绑定具体实现类或引入新的抽象基类。

原因：

- 具体类类型会把 wiring 绑死到当前实现，不利于 stub/fake/替换 provider
- `ABC` 需要现有实现显式继承，侵入性较高
- `Protocol` 可以只表达“调用方真正依赖的方法”，对现有实现零继承要求

新增一个共享类型接口模块，集中定义最小协议。

建议协议：

```python
class EmbeddingProvider(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...
    def model_name(self) -> str: ...
    def embedding_dimension(self) -> int: ...


class VlmClientLike(Protocol):
    def describe_image(self, image_path: Path) -> str: ...


class RerankerLike(Protocol):
    def rerank(self, query: str, candidates: list[dict]) -> list[dict]: ...
```

协议保持“最小可用”原则：

- `EmbeddingProvider` 覆盖 indexing 中已使用的方法，并保留 query embedding 能力，避免后续 retrieval/vector 查询再次回退到 `Any`
- `VlmClientLike` 只暴露当前 resource extraction 依赖的 `describe_image`
- `RerankerLike` 只暴露当前 retrieval pipeline 依赖的 `rerank`

---

## 4. 代码范围

本次修改覆盖以下依赖注入边界：

- `src/rag_mcp/transport/handlers.py`
- `src/rag_mcp/indexing/rebuild.py`
- `src/rag_mcp/indexing/services.py`
- `src/rag_mcp/indexing/resource_store.py`
- `src/rag_mcp/retrieval/service.py`

必要时同步检查 bootstrap / factory / tests 中对这些构造器的调用。

---

## 5. 清理原则

### 5.1 只收紧接口，不扩大重构

如果某处 `Any` 实际是注入对象，则替换为协议类型。

如果某处 `Any` 是 JSON payload 或 metadata 的一部分，则保持不动。

### 5.2 顺手清理无效注入

若某个注入参数已不再被行为使用，应评估是否删除，避免“被类型化但仍是死参数”。

当前已识别的重点是 retrieval service 的 `embedding_provider`。如果确认该对象未参与任何行为，则应从该 service 构造器移除，而不是继续保留一个未使用的强类型参数。

### 5.3 协议放在共享位置

协议不应散落在各模块内部，否则后续又会重复定义同义接口。应集中放在单一模块，供 transport / indexing / retrieval 共用。

---

## 6. 测试策略

遵循 TDD，先写失败测试，再做实现。

至少补以下测试：

- 现有实现类满足协议约束的静态/实例化用例
- `ToolHandlers` 可接受符合协议的 stub provider/client/reranker
- `RebuildIndexService` / `ResourceStore` / `RetrievalService` 仍可接受最小 stub 对象
- 若移除未使用注入参数，补充对应构造器回归测试

测试重点不是证明具体实现细节，而是证明运行时装配边界已经从 `Any` 收紧为明确接口，且不破坏现有行为。

---

## 7. 完成标准

- 目标范围内的依赖注入型 `Any` 被协议类型替换
- 未使用的注入参数不再继续传播
- 相关单元测试覆盖协议兼容和构造回归
- 不修改外部 tool contract
- 不处理 payload/metadata 型 `Any`
