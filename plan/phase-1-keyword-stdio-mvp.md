# Phase 1: Keyword + Stdio MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付一个本地可运行的 stdio MCP 服务，支持全量重建、关键词检索、`rag://` 资源回读。

**Architecture:** 先落地最小可用闭环：配置/错误/XML 契约 -> 文档导入与分块 -> 关键词索引与原子切换 -> MCP 工具与资源读取。`vector` 模式在本阶段只返回“未实现”错误码。

**Tech Stack:** Python 3.13, pytest, FastMCP(或官方 Python SDK), rank-bm25, lxml/xml.etree, pydantic

---

## 0) Plan Review（开发前必须完成）

- [x] 已确认本 Phase 仅覆盖：`keyword` + `stdio`，不提前实现 `vector`/HTTP。
- [x] 已确认 XML 契约与错误码命名与 RFC 一致。
- [x] 已确认目录与模块边界遵守 RFC 单向依赖。
- [x] 已确认验收命令可在本仓库直接执行。
- [x] Reviewer: Codex
- [x] Review Date: 2026-03-28

## 1) 文件规划

**Create**
- `src/rag_mcp/__init__.py`
- `src/rag_mcp/config.py`
- `src/rag_mcp/errors.py`
- `src/rag_mcp/xml_response.py`
- `src/rag_mcp/models.py`
- `src/rag_mcp/ingestion/filesystem.py`
- `src/rag_mcp/chunking/chunker.py`
- `src/rag_mcp/indexing/manifest.py`
- `src/rag_mcp/indexing/keyword_index.py`
- `src/rag_mcp/indexing/rebuild.py`
- `src/rag_mcp/retrieval/service.py`
- `src/rag_mcp/resources/uri.py`
- `src/rag_mcp/resources/service.py`
- `src/rag_mcp/transport/stdio_server.py`
- `tests/unit/test_config.py`
- `tests/unit/test_xml_response.py`
- `tests/unit/test_chunker.py`
- `tests/unit/test_keyword_index.py`
- `tests/integration/test_phase1_stdio_keyword_flow.py`
- `tests/fixtures/corpus_phase1/README.md`
- `tests/fixtures/corpus_phase1/notes.txt`

**Modify**
- `pyproject.toml`
- `main.py`
- `README.md`

## 2) 原子化 TDD Tasks

### Task 1: 配置与错误模型基线

- [x] Step 1 (Failing Test): 新增 `tests/unit/test_config.py` 与 `tests/unit/test_xml_response.py`，定义环境变量加载、默认参数、错误 XML 结构断言。
- [x] Step 2 (Verify Fail): 运行 `pytest tests/unit/test_config.py tests/unit/test_xml_response.py -q`，预期 FAIL（模块不存在）。
- [x] Step 3 (Minimal Code): 实现 `config.py`、`errors.py`、`xml_response.py`，覆盖 `NO_ACTIVE_INDEX`、`UNSUPPORTED_SEARCH_MODE`、`SEARCH_MODE_NOT_IMPLEMENTED`。
- [x] Step 4 (Verify Pass): 再次运行同一命令，预期 PASS。
- [x] Step 5 (Commit): `git add src/rag_mcp/config.py src/rag_mcp/errors.py src/rag_mcp/xml_response.py tests/unit/test_config.py tests/unit/test_xml_response.py && git commit -m "feat: add config and xml error envelope"`

### Task 2: 文档导入与分块（md/txt）

- [x] Step 1 (Failing Test): 新增 `tests/unit/test_chunker.py`，覆盖标题优先切分、fallback 递归切分、`chunk_index` 连续性。
- [x] Step 2 (Verify Fail): 运行 `pytest tests/unit/test_chunker.py -q`，预期 FAIL。
- [x] Step 3 (Minimal Code): 实现 `ingestion/filesystem.py` 与 `chunking/chunker.py`，仅支持 `.md`/`.txt`，输出统一 `Chunk` 模型及 `heading_path` 元信息。
- [x] Step 4 (Verify Pass): 运行 `pytest tests/unit/test_chunker.py -q`，预期 PASS。
- [x] Step 5 (Commit): `git add src/rag_mcp/ingestion/filesystem.py src/rag_mcp/chunking/chunker.py src/rag_mcp/models.py tests/unit/test_chunker.py tests/fixtures/corpus_phase1 && git commit -m "feat: add ingestion and chunking for md/txt"`

### Task 3: 全量重建 + 活动索引清单 + 关键词索引

- [x] Step 1 (Failing Test): 新增 `tests/unit/test_keyword_index.py`，覆盖全量重建、活动索引切换、失败回滚到旧索引。
- [x] Step 2 (Verify Fail): 运行 `pytest tests/unit/test_keyword_index.py -q`，预期 FAIL。
- [x] Step 3 (Minimal Code): 实现 `indexing/manifest.py`、`indexing/keyword_index.py`、`indexing/rebuild.py`，写入 `active_index.json` 与关键词检索存储。
- [x] Step 4 (Verify Pass): 运行 `pytest tests/unit/test_keyword_index.py -q`，预期 PASS。
- [x] Step 5 (Commit): `git add src/rag_mcp/indexing tests/unit/test_keyword_index.py && git commit -m "feat: add atomic rebuild and keyword index"`

### Task 4: 检索服务 + 资源 URI 读取

- [x] Step 1 (Failing Test): 在 `tests/integration/test_phase1_stdio_keyword_flow.py` 增加 `rag_search(keyword)`、`rag://` 回读、`vector` 未实现错误语义断言。
- [x] Step 2 (Verify Fail): 运行 `pytest tests/integration/test_phase1_stdio_keyword_flow.py -q`，预期 FAIL。
- [x] Step 3 (Minimal Code): 实现 `retrieval/service.py`、`resources/uri.py`、`resources/service.py`，确保返回字段 `text/title/uri/score/metadata`。
- [x] Step 4 (Verify Pass): 运行同一命令，预期 PASS。
- [x] Step 5 (Commit): `git add src/rag_mcp/retrieval src/rag_mcp/resources tests/integration/test_phase1_stdio_keyword_flow.py && git commit -m "feat: add keyword retrieval and rag resource reader"`

### Task 5: MCP stdio 接线与端到端可运行

- [x] Step 1 (Failing Test): 扩展 `tests/integration/test_phase1_stdio_keyword_flow.py`，验证 `rag_rebuild_index` / `rag_index_status` / `rag_search` XML 结构与错误结构。
- [x] Step 2 (Verify Fail): 运行 `pytest tests/integration/test_phase1_stdio_keyword_flow.py -q`，预期 FAIL。
- [x] Step 3 (Minimal Code): 实现 `transport/stdio_server.py`，在 `main.py` 提供启动入口；`README.md` 增加最小运行说明。
- [x] Step 4 (Verify Pass): 运行 `pytest tests/integration/test_phase1_stdio_keyword_flow.py -q`，预期 PASS。
- [x] Step 5 (Commit): `git add src/rag_mcp/transport/stdio_server.py main.py README.md tests/integration/test_phase1_stdio_keyword_flow.py && git commit -m "feat: wire stdio transport for phase1"`

## 3) Phase 1 验收（可运行 + 可签收）

- [x] `pytest tests/unit tests/integration/test_phase1_stdio_keyword_flow.py -q` 全通过。
- [x] 手动启动：`python -m rag_mcp.transport.stdio_server` 可启动并响应工具调用。（验证命令：`PYTHONPATH=src python3 -m rag_mcp.transport.stdio_server`）
- [x] 手动验收：同一目录重复重建后 `corpus_id` 稳定；`rag://` 资源可回读。
- [x] 手动验收：`mode=vector` 返回 `SEARCH_MODE_NOT_IMPLEMENTED`。

## 4) 签收记录

- [x] Phase Owner: Codex
- [x] QA/Reviewer: Pending user sign-off
- [x] Sign-off Date: 2026-03-28
- [x] Sign-off Commit: 78e3076
- [x] Notes: Phase 1 implementation and verification completed; waiting for user acceptance.
