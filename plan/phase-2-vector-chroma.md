# Phase 2: Vector + Chroma + Embedding 一致性 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Phase 1 基线之上增加 `vector` 模式检索，落地 Chroma 持久化向量索引，并实现 RFC 规定的配置一致性错误语义。

**Architecture:** 保持统一重建流程同时产出 keyword/vector 两类索引；检索时按 `mode` 路由。向量模式依赖 embedding 客户端与 manifest 校验，确保索引配置与运行配置一致。

**Tech Stack:** Python 3.13, pytest, chromadb, SiliconFlow Embeddings API（OpenAI-compatible）, pydantic

---

## 0) Plan Review（开发前必须完成）

- [ ] 已确认 Phase 2 不改动 Phase 1 已签收契约（XML 根结构、错误模型、URI 语法）。
- [ ] 已确认 `VECTOR_INDEX_CONFIG_MISMATCH` 语义只影响 `vector`，不影响 `keyword` 与 `rag://` 读取。
- [ ] 已确认 `hybrid`/`rerank` 仍保持“保留未实现”状态。
- [ ] 已确认需要的新环境变量、默认值与文档更新项。
- [ ] Reviewer:
- [ ] Review Date:

## 1) 文件规划

**Create**
- `src/rag_mcp/embedding/client.py`
- `src/rag_mcp/indexing/vector_index.py`
- `tests/unit/test_embedding_client.py`
- `tests/unit/test_vector_index.py`
- `tests/integration/test_phase2_vector_keyword_parity.py`
- `tests/fixtures/corpus_phase2/reference.md`

**Modify**
- `src/rag_mcp/config.py`
- `src/rag_mcp/errors.py`
- `src/rag_mcp/indexing/manifest.py`
- `src/rag_mcp/indexing/rebuild.py`
- `src/rag_mcp/retrieval/service.py`
- `src/rag_mcp/transport/stdio_server.py`
- `pyproject.toml`
- `README.md`

## 2) 原子化 TDD Tasks

### Task 1: Embedding 客户端与配置校验

- [ ] Step 1 (Failing Test): 新增 `tests/unit/test_embedding_client.py`，覆盖缺失 API Key、模型名、超时配置的错误行为。
- [ ] Step 2 (Verify Fail): 运行 `pytest tests/unit/test_embedding_client.py -q`，预期 FAIL。
- [ ] Step 3 (Minimal Code): 实现 `embedding/client.py`，并在 `config.py` 增加 `EMBEDDING_API_KEY`、`EMBEDDING_MODEL`、`EMBEDDING_BASE_URL`、`EMBEDDING_DIMENSION`（默认对接 `https://api.siliconflow.cn/v1`）。
- [ ] Step 4 (Verify Pass): 运行同一命令，预期 PASS。
- [ ] Step 5 (Commit): `git add src/rag_mcp/embedding src/rag_mcp/config.py tests/unit/test_embedding_client.py && git commit -m "feat: add embedding client and config validation"`

### Task 2: Chroma 向量索引构建与持久化

- [ ] Step 1 (Failing Test): 新增 `tests/unit/test_vector_index.py`，覆盖向量入库、重建覆盖、查询 top-k 基本排序。
- [ ] Step 2 (Verify Fail): 运行 `pytest tests/unit/test_vector_index.py -q`，预期 FAIL。
- [ ] Step 3 (Minimal Code): 实现 `indexing/vector_index.py`，在 `indexing/rebuild.py` 里并入统一重建流程（keyword + vector 同步更新）。
- [ ] Step 4 (Verify Pass): 运行同一命令，预期 PASS。
- [ ] Step 5 (Commit): `git add src/rag_mcp/indexing/vector_index.py src/rag_mcp/indexing/rebuild.py tests/unit/test_vector_index.py && git commit -m "feat: add chroma vector indexing in rebuild pipeline"`

### Task 3: Manifest 扩展与配置一致性错误码

- [ ] Step 1 (Failing Test): 扩展 `tests/unit/test_vector_index.py`，断言 manifest 存储 `embedding_model` 与 `embedding_dimension`，并在不一致时抛 `VECTOR_INDEX_CONFIG_MISMATCH`。
- [ ] Step 2 (Verify Fail): 运行 `pytest tests/unit/test_vector_index.py -q`，预期 FAIL。
- [ ] Step 3 (Minimal Code): 更新 `indexing/manifest.py`、`errors.py`、`retrieval/service.py` 一致性校验路径。
- [ ] Step 4 (Verify Pass): 运行同一命令，预期 PASS。
- [ ] Step 5 (Commit): `git add src/rag_mcp/indexing/manifest.py src/rag_mcp/errors.py src/rag_mcp/retrieval/service.py tests/unit/test_vector_index.py && git commit -m "feat: enforce vector index config compatibility"`

### Task 4: `rag_search(vector)` 与模式语义

- [ ] Step 1 (Failing Test): 新增 `tests/integration/test_phase2_vector_keyword_parity.py`，覆盖 `mode=vector|keyword`、`mode=hybrid|rerank` 错误语义、结果字段一致性。
- [ ] Step 2 (Verify Fail): 运行 `pytest tests/integration/test_phase2_vector_keyword_parity.py -q`，预期 FAIL。
- [ ] Step 3 (Minimal Code): 更新 `retrieval/service.py` 与 `transport/stdio_server.py` 的模式路由与 XML 输出。
- [ ] Step 4 (Verify Pass): 运行同一命令，预期 PASS。
- [ ] Step 5 (Commit): `git add src/rag_mcp/retrieval/service.py src/rag_mcp/transport/stdio_server.py tests/integration/test_phase2_vector_keyword_parity.py && git commit -m "feat: add vector search mode with reserved-mode errors"`

### Task 5: 回归与文档更新

- [ ] Step 1 (Failing Test): 将 Phase 1 集成测试与 Phase 2 集成测试合并运行，记录潜在回归失败。
- [ ] Step 2 (Verify Fail): 运行 `pytest tests/integration/test_phase1_stdio_keyword_flow.py tests/integration/test_phase2_vector_keyword_parity.py -q`，若失败先定位并补测试。
- [ ] Step 3 (Minimal Code): 修复回归并更新 `README.md` 的环境变量与本地运行说明。
- [ ] Step 4 (Verify Pass): 运行 `pytest tests/unit tests/integration/test_phase1_stdio_keyword_flow.py tests/integration/test_phase2_vector_keyword_parity.py -q`，预期 PASS。
- [ ] Step 5 (Commit): `git add README.md tests src/rag_mcp && git commit -m "chore: phase2 regression pass and docs update"`

## 3) Phase 2 验收（可运行 + 可签收）

- [ ] `keyword` 与 `vector` 模式均可返回结果，并共享同一 `rag://` 资源寻址规则。
- [ ] `mode=hybrid`、`mode=rerank` 返回 `SEARCH_MODE_NOT_IMPLEMENTED`。
- [ ] embedding 配置与活动索引不一致时，仅 `vector` 返回 `VECTOR_INDEX_CONFIG_MISMATCH`。
- [ ] `pytest tests/unit tests/integration/test_phase1_stdio_keyword_flow.py tests/integration/test_phase2_vector_keyword_parity.py -q` 全通过。

## 4) 签收记录

- [ ] Phase Owner:
- [ ] QA/Reviewer:
- [ ] Sign-off Date:
- [ ] Sign-off Commit:
- [ ] Notes:
