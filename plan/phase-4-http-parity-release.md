# Phase 4: HTTP 对等传输 + 发布验收 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在已签收的 stdio 能力基础上提供显式启用的 HTTP 传输，并确保两种传输对工具契约、资源读取与错误模型行为一致，形成可交付 v1 候选版本。

**Architecture:** 通过共享 handler/service 层实现传输适配器薄层化。HTTP 默认关闭，只有配置启用时监听端口，保持本地优先与最小暴露面。

**Tech Stack:** Python 3.13, pytest, FastMCP/official MCP SDK, uvicorn(or sdk builtin http server)

---

## 0) Plan Review（开发前必须完成）

- [x] 已确认 HTTP 默认为关闭状态，避免默认网络暴露。
- [x] 已确认 stdio/HTTP 的 XML 成功与错误结构完全一致。
- [x] 已确认路径校验与敏感信息约束（不泄露绝对路径）覆盖到测试。
- [x] 已确认发布前回归范围包含 Phase 1-3 全套关键链路。
- [x] Reviewer: Codex
- [x] Review Date: 2026-03-28

## 1) 文件规划

**Create**
- `src/rag_mcp/transport/handlers.py`
- `src/rag_mcp/transport/http_server.py`
- `tests/integration/test_phase4_http_stdio_parity.py`
- `tests/e2e/test_v1_acceptance.py`
- `scripts/e2e_phase4_smoke.sh`

**Modify**
- `src/rag_mcp/config.py`
- `src/rag_mcp/transport/stdio_server.py`
- `src/rag_mcp/xml_response.py`
- `main.py`
- `README.md`
- `pyproject.toml`

## 2) 原子化 TDD Tasks

### Task 1: 共享 Handler 抽象

- [x] Step 1 (Failing Test): 新增 `tests/integration/test_phase4_http_stdio_parity.py` 的基础用例，断言同一输入下 stdio 与 HTTP 返回 XML 完全一致。
- [x] Step 2 (Verify Fail): 运行 `pytest tests/integration/test_phase4_http_stdio_parity.py -q`，预期 FAIL。
- [x] Step 3 (Minimal Code): 实现 `transport/handlers.py`，将工具逻辑从 `stdio_server.py` 抽离为可复用 handler。
- [x] Step 4 (Verify Pass): 运行同一命令，预期 PASS。
- [x] Step 5 (Commit): `git add src/rag_mcp/transport/handlers.py src/rag_mcp/transport/stdio_server.py tests/integration/test_phase4_http_stdio_parity.py && git commit -m "refactor: share tool handlers across transports"`

### Task 2: HTTP 入口与显式启用策略

- [x] Step 1 (Failing Test): 扩展 `tests/integration/test_phase4_http_stdio_parity.py`，覆盖 `ENABLE_HTTP=false` 不启动监听，`ENABLE_HTTP=true` 可访问。
- [x] Step 2 (Verify Fail): 运行 `pytest tests/integration/test_phase4_http_stdio_parity.py -q`，预期 FAIL。
- [x] Step 3 (Minimal Code): 实现 `transport/http_server.py`，更新 `config.py` 与 `main.py` 启动分支。
- [x] Step 4 (Verify Pass): 运行同一命令，预期 PASS。
- [x] Step 5 (Commit): `git add src/rag_mcp/transport/http_server.py src/rag_mcp/config.py main.py tests/integration/test_phase4_http_stdio_parity.py && git commit -m "feat: add opt-in http transport"`

### Task 3: 安全约束与错误细节一致性

- [x] Step 1 (Failing Test): 在 `tests/integration/test_phase4_http_stdio_parity.py` 增加非法目录、空目录、资源不存在等错误用例，断言 `code/message/hint` 一致。
- [x] Step 2 (Verify Fail): 运行 `pytest tests/integration/test_phase4_http_stdio_parity.py -q`，预期 FAIL。
- [x] Step 3 (Minimal Code): 更新目录校验、错误映射、XML 输出，确保不暴露本地绝对路径。
- [x] Step 4 (Verify Pass): 运行同一命令，预期 PASS。
- [x] Step 5 (Commit): `git add src/rag_mcp tests/integration/test_phase4_http_stdio_parity.py && git commit -m "feat: enforce transport-safe error semantics"`

### Task 4: 端到端验收脚本与发布文档

- [x] Step 1 (Failing Test): 新增 `tests/e2e/test_v1_acceptance.py`，覆盖重建 -> keyword/vector 搜索 -> `rag://` 回读（stdio+HTTP）。
- [x] Step 2 (Verify Fail): 运行 `pytest tests/e2e/test_v1_acceptance.py -q`，预期 FAIL。
- [x] Step 3 (Minimal Code): 新增 `scripts/e2e_phase4_smoke.sh`，更新 `README.md` 运行手册与环境变量表。
- [x] Step 4 (Verify Pass): 运行 `pytest tests/e2e/test_v1_acceptance.py -q` 与 `bash scripts/e2e_phase4_smoke.sh`，预期 PASS。
- [x] Step 5 (Commit): `git add tests/e2e scripts/e2e_phase4_smoke.sh README.md pyproject.toml && git commit -m "docs: add v1 runbook and e2e smoke checks"`

### Task 5: 全量回归与发布候选冻结

- [ ] Step 1 (Failing Test): 先运行全量测试收集失败项 `pytest -q`。
- [ ] Step 2 (Verify Fail): 若存在失败，先补回归测试再修复，不跳过失败。
- [ ] Step 3 (Minimal Code): 修复所有回归，保持 API 契约不破坏。
- [ ] Step 4 (Verify Pass): 再次运行 `pytest -q`，预期 PASS。
- [ ] Step 5 (Commit): `git add src tests README.md && git commit -m "release: phase4 candidate with full regression pass"`

## 3) Phase 4 验收（可运行 + 可签收）

- [ ] stdio 与 HTTP 对同一请求返回语义一致（字段、错误码、hint 一致）。
- [ ] HTTP 默认关闭，显式启用后可正常服务。
- [ ] `pytest -q` 全通过。
- [ ] `bash scripts/e2e_phase4_smoke.sh` 全通过。

## 4) 签收记录

- [ ] Phase Owner:
- [ ] QA/Reviewer:
- [ ] Sign-off Date:
- [ ] Sign-off Commit:
- [ ] Notes:
