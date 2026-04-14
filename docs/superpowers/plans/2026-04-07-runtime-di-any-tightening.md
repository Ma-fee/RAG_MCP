# Runtime DI Any Tightening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `phase4-runtime-merge` 中依赖注入边界上的 `Any` 收紧为明确协议类型，并清理未使用注入参数，不改变外部 tool contract。

**Architecture:** 新增一个共享协议模块，集中定义 embedding provider、VLM client、reranker 的最小运行时接口；transport/indexing/retrieval 统一引用这些协议而不是 `Any`。对确认未参与行为的注入参数直接删除，避免把死参数“类型化后继续传播”。

**Tech Stack:** Python 3.13, pytest, dataclasses, typing.Protocol

---

## 0) Plan Review

- [ ] 已确认本任务只处理依赖注入型 `Any`。
- [ ] 已确认不处理 `dict[str, Any]`、`metadata: dict[str, Any]`。
- [ ] 已确认不修改外部 tool contract。
- [ ] 已确认允许删除未使用注入参数。
- [ ] Reviewer: Pending
- [ ] Review Date: 2026-04-07

## 1) 文件规划

**Create**
- `src/rag_mcp/runtime_types.py`
- `tests/unit/test_runtime_types.py`

**Modify**
- `src/rag_mcp/transport/handlers.py`
- `src/rag_mcp/indexing/rebuild.py`
- `src/rag_mcp/indexing/services.py`
- `src/rag_mcp/indexing/resource_store.py`
- `src/rag_mcp/retrieval/service.py`
- `tests/unit/test_handlers_dict.py`
- `tests/unit/test_resource_store.py`
- `tests/unit/test_vector_index.py`
- `tests/unit/test_hybrid_search.py`
- `tests/unit/test_rerank.py`

## 2) 原子化 TDD Tasks

### Task 1: 新增共享运行时协议

**Files:**
- Create: `src/rag_mcp/runtime_types.py`
- Test: `tests/unit/test_runtime_types.py`

- [ ] **Step 1: 写失败测试**

```python
from pathlib import Path

from rag_mcp.embedding.client import EmbeddingClient
from rag_mcp.ingestion.vlm_client import VlmClient
from rag_mcp.retrieval.reranker import ApiReranker
from rag_mcp.runtime_types import EmbeddingProvider, RerankerLike, VlmClientLike


def test_runtime_types_protocols_accept_real_implementations() -> None:
    def accept_embedding(provider: EmbeddingProvider | None) -> EmbeddingProvider | None:
        return provider

    def accept_vlm(client: VlmClientLike | None) -> VlmClientLike | None:
        return client

    def accept_reranker(reranker: RerankerLike | None) -> RerankerLike | None:
        return reranker

    assert accept_embedding(None) is None
    assert accept_vlm(None) is None
    assert accept_reranker(None) is None

    assert EmbeddingClient.embed_documents
    assert EmbeddingClient.embed_query
    assert EmbeddingClient.model_name
    assert EmbeddingClient.embedding_dimension
    assert VlmClient.describe_image
    assert ApiReranker.rerank
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
uv run pytest -q tests/unit/test_runtime_types.py
```

Expected: FAIL，因为 `rag_mcp.runtime_types` 不存在。

- [ ] **Step 3: 写最小实现**

```python
from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class EmbeddingProvider(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...
    def model_name(self) -> str: ...
    def embedding_dimension(self) -> int: ...


class VlmClientLike(Protocol):
    def describe_image(self, image_path: Path) -> str: ...


class RerankerLike(Protocol):
    def rerank(self, query: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]: ...
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
uv run pytest -q tests/unit/test_runtime_types.py
```

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add src/rag_mcp/runtime_types.py tests/unit/test_runtime_types.py
git commit -m "refactor: add runtime dependency protocols"
```

### Task 2: 收紧 ResourceStore 和 rebuild path 的 VLM / embedding 注入类型

**Files:**
- Modify: `src/rag_mcp/indexing/resource_store.py`
- Modify: `src/rag_mcp/indexing/services.py`
- Modify: `src/rag_mcp/indexing/rebuild.py`
- Test: `tests/unit/test_resource_store.py`

- [ ] **Step 1: 写失败测试**

```python
from pathlib import Path

from rag_mcp.indexing.resource_store import ResourceStore


class StubVlmClient:
    def describe_image(self, image_path: Path) -> str:
        return f"desc:{image_path.name}"


def test_resource_store_accepts_protocol_vlm_stub(tmp_path: Path) -> None:
    store = ResourceStore(index_dir=tmp_path, corpus_id="c1", vlm_client=StubVlmClient())

    assert store.vlm_client is not None
    assert store.vlm_client.describe_image(Path("image.png")) == "desc:image.png"
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
uv run pytest -q tests/unit/test_resource_store.py::test_resource_store_accepts_protocol_vlm_stub
```

Expected: FAIL，因为测试尚不存在或属性类型尚未收口。

- [ ] **Step 3: 写最小实现**

```python
from rag_mcp.runtime_types import EmbeddingProvider, VlmClientLike
```

```python
class ResourceStore:
    vlm_client: VlmClientLike | None
```

```python
def rebuild_keyword_index(
    *,
    source_dir: Path,
    data_dir: Path,
    embedding_provider: EmbeddingProvider | None = None,
    vlm_client: VlmClientLike | None = None,
) -> dict[str, Any]:
    ...
```

```python
class RebuildIndexService:
    def rebuild_keyword_index(
        self,
        *,
        source_dir: Path,
        data_dir: Path,
        min_chunk_length: int = 30,
        embedding_provider: EmbeddingProvider | None = None,
        vlm_client: VlmClientLike | None = None,
    ) -> dict[str, Any]:
        ...
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
uv run pytest -q tests/unit/test_resource_store.py
```

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add src/rag_mcp/indexing/resource_store.py src/rag_mcp/indexing/services.py src/rag_mcp/indexing/rebuild.py tests/unit/test_resource_store.py
git commit -m "refactor: type runtime providers in rebuild path"
```

### Task 3: 收紧 ToolHandlers 和 RetrievalService 的 reranker 注入，并删除未使用的 embedding_provider 注入

**Files:**
- Modify: `src/rag_mcp/transport/handlers.py`
- Modify: `src/rag_mcp/retrieval/service.py`
- Test: `tests/unit/test_handlers_dict.py`
- Modify/Test: `tests/unit/test_vector_index.py`
- Modify/Test: `tests/unit/test_hybrid_search.py`
- Modify/Test: `tests/unit/test_rerank.py`

- [ ] **Step 1: 写失败测试**

```python
from pathlib import Path

from rag_mcp.transport.handlers import ToolHandlers


class StubEmbeddingProvider:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [0.1]

    def model_name(self) -> str:
        return "stub"

    def embedding_dimension(self) -> int:
        return 1


class StubReranker:
    def rerank(self, query: str, candidates: list[dict[str, object]]) -> list[dict[str, object]]:
        return candidates


def test_tool_handlers_accept_protocol_stubs(tmp_path: Path) -> None:
    handlers = ToolHandlers(
        data_dir=tmp_path,
        embedding_provider=StubEmbeddingProvider(),
        vlm_client=None,
        reranker=StubReranker(),
    )

    assert handlers.embedding_provider is not None
    assert handlers.retrieval is not None
```
```
def test_retrieval_service_does_not_accept_embedding_provider_argument(tmp_path: Path) -> None:
    RetrievalService(data_dir=tmp_path, embedding_provider=None)
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
uv run pytest -q tests/unit/test_handlers_dict.py::test_tool_handlers_accept_protocol_stubs tests/unit/test_vector_index.py tests/unit/test_hybrid_search.py tests/unit/test_rerank.py
```

Expected: FAIL，原因包括测试未添加，以及旧测试仍在向 `RetrievalService` 传 `embedding_provider`。

- [ ] **Step 3: 写最小实现**

```python
from rag_mcp.runtime_types import EmbeddingProvider, RerankerLike, VlmClientLike
```

```python
class ToolHandlers:
    def __init__(
        self,
        data_dir: Path,
        embedding_provider: EmbeddingProvider | None = None,
        vlm_client: VlmClientLike | None = None,
        reranker: RerankerLike | None = None,
        rerank_top_k_candidates: int = 20,
    ) -> None:
        ...
        self.retrieval = RetrievalService(
            self.data_dir,
            reranker=reranker,
            rerank_top_k_candidates=rerank_top_k_candidates,
        )
```

```python
class RetrievalService:
    def __init__(
        self,
        data_dir: Path,
        reranker: RerankerLike | None = None,
        rerank_top_k_candidates: int = 20,
    ) -> None:
        ...
```

并同步删除测试中对 `RetrievalService(..., embedding_provider=...)` 的调用，改成只构造真正参与行为的依赖。

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
uv run pytest -q tests/unit/test_handlers_dict.py tests/unit/test_vector_index.py tests/unit/test_hybrid_search.py tests/unit/test_rerank.py
```

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add src/rag_mcp/transport/handlers.py src/rag_mcp/retrieval/service.py tests/unit/test_handlers_dict.py tests/unit/test_vector_index.py tests/unit/test_hybrid_search.py tests/unit/test_rerank.py
git commit -m "refactor: tighten handler and retrieval dependency types"
```

### Task 4: 回归验证运行时 DI 类型收口

**Files:**
- Modify: `src/rag_mcp/runtime_types.py`
- Modify: `src/rag_mcp/transport/handlers.py`
- Modify: `src/rag_mcp/indexing/rebuild.py`
- Modify: `src/rag_mcp/indexing/services.py`
- Modify: `src/rag_mcp/indexing/resource_store.py`
- Modify: `src/rag_mcp/retrieval/service.py`
- Test: `tests/unit/test_runtime_types.py`
- Test: `tests/unit/test_handlers_dict.py`
- Test: `tests/unit/test_resource_store.py`
- Test: `tests/unit/test_vector_index.py`
- Test: `tests/unit/test_hybrid_search.py`
- Test: `tests/unit/test_rerank.py`

- [ ] **Step 1: 运行聚焦测试**

Run:

```bash
uv run pytest -q tests/unit/test_runtime_types.py tests/unit/test_handlers_dict.py tests/unit/test_resource_store.py tests/unit/test_vector_index.py tests/unit/test_hybrid_search.py tests/unit/test_rerank.py
```

Expected: PASS。

- [ ] **Step 2: 运行关键回归测试**

Run:

```bash
uv run pytest -q tests/integration/test_phase3_structure_and_uri_stability.py tests/integration/test_e2e_multimodal.py
```

Expected: PASS。

- [ ] **Step 3: 检查目标文件中的依赖注入型 `Any` 已移除**

Run:

```bash
rg -n "embedding_provider: Any|vlm_client: Any|reranker: Any|embedding_provider: Any \\| None|vlm_client: Any \\| None|reranker: Any \\| None" src/rag_mcp/transport/handlers.py src/rag_mcp/indexing/rebuild.py src/rag_mcp/indexing/services.py src/rag_mcp/indexing/resource_store.py src/rag_mcp/retrieval/service.py
```

Expected: 无输出。

- [ ] **Step 4: 提交**

```bash
git add src/rag_mcp/runtime_types.py src/rag_mcp/transport/handlers.py src/rag_mcp/indexing/rebuild.py src/rag_mcp/indexing/services.py src/rag_mcp/indexing/resource_store.py src/rag_mcp/retrieval/service.py tests/unit/test_runtime_types.py tests/unit/test_handlers_dict.py tests/unit/test_resource_store.py tests/unit/test_vector_index.py tests/unit/test_hybrid_search.py tests/unit/test_rerank.py
git commit -m "refactor: remove runtime dependency anys"
```
