# Phase 4 Runtime Assembly Cleanup Implementation Record

> Status Date: 2026-04-07  
> Workspace: `/Users/admin/Downloads/rag_mcp/.worktrees/phase1-service-boundary-cleanup`

## 0) Scope Guardrails

- [x] 不修改外部 tool contract（对外 key 结构保持兼容）。
- [x] 不重做 domain service 的业务语义，仅做边界与装配清理。
- [x] 运行时装配路径与测试装配路径尽量复用同一 build path。

## 1) Task Breakdown and Implementation Status

### Task 1: AppConfig 分层（runtime/provider/retrieval）

- [x] 已实现分层配置模型并保持兼容字段访问。
- [x] 已补/改配置模型测试，验证 env -> nested config 行为。
- [x] 关键验证：
  - `uv run pytest -q tests/unit/test_config_models.py tests/unit/test_config.py`

### Task 2: bootstrap / app factory 抽离

- [x] 已新增 `src/rag_mcp/bootstrap.py`，提供统一装配入口。
- [x] `main.py` 已变薄，改为委托 bootstrap + runtime runner。
- [x] 关键验证：
  - `uv run pytest -q tests/unit/test_bootstrap.py tests/unit/test_main.py`

### Task 3: transport runtime runner 统一

- [x] 已新增 `src/rag_mcp/transport/runtime.py`，统一 stdio/sse/streamable-http 运行分支。
- [x] 已补 runtime 单测，覆盖 transport 分支调度行为。
- [x] 关键验证：
  - `uv run pytest -q tests/unit/test_transport_runtime.py tests/unit/test_mcp_server.py`

### Task 4: 测试装配与运行时装配对齐

- [x] 已新增 `tests/helpers/app_factory.py`，测试复用构建路径。
- [x] 关键测试已切到统一装配 helper，减少散装依赖拼接。
- [x] 关键验证：
  - `uv run pytest -q tests/unit/test_fastapi_app.py tests/unit/test_bootstrap.py tests/unit/test_transport_runtime.py`

## 2) Post-Task Stabilization (Regression Hardening)

### Stabilization A: indexing compatibility

- [x] `RebuildIndexService` 恢复非 PDF fallback chunking，避免 md/txt 被 TOC-only 路径阻断。
- [x] PDF TOC 失败/缺失时改为 fallback，不阻断重建主流程。

### Stabilization B: retrieval compatibility

- [x] 在 `retrieval/service.py` 补回 `read_active_manifest` 兼容入口，保持历史 patch 点可用。

### Stabilization C: resource contract compatibility

- [x] `resource_store` 的 image/table 条目恢复 `caption` 字段。
- [x] `ChunkAssembler` 纳入 `image` element，确保 `resource_metadata.image_element_ids` 在结构化场景下完整。

### Stabilization D: rebuild patch compatibility

- [x] `indexing/rebuild.py` 补回 `_build_and_persist_keyword_store` patch 兼容入口，保障旧测试 monkeypatch 路径稳定。

## 3) Interface Convergence (Transport Input Boundary)

- [x] 新增 `src/rag_mcp/transport/schemas.py`（pydantic v2 输入模型）。
- [x] `ToolHandlers` 改为统一通过 schema 解析/归一化输入：
  - `search`
  - `read_resource`
  - `list_sections`
  - `section_retrieval`
- [x] 保持外部返回结构不变，错误仍映射为 `{ "error": "...", "message": "..." }`。

## 4) Verification Evidence

- [x] 单元全量：
  - `uv run pytest -q tests/unit`
  - Result: `175 passed`（阶段中间态）→ 后续变更后再次全量通过。
- [x] 关键 unit + integration 联跑：
  - `uv run pytest -q tests/unit tests/integration/test_phase3_structure_and_uri_stability.py tests/integration/test_e2e_multimodal.py`
  - Result: `185 passed, 6 warnings`
- [x] integration 全量：
  - `uv run pytest -q tests/integration`
  - Result: `6 passed, 5 warnings`

## 5) Acceptance Snapshot

- [x] runtime 装配路径已统一（bootstrap + runtime runner）。
- [x] transport 输入边界已收敛（pydantic schema）。
- [x] 外部 tool contract 保持兼容。
- [x] unit + integration 回归通过，可进入提交/签收阶段。

## 6) Next Action (Execution Order)

1. 在本 worktree 提交本轮变更（建议拆 2-3 个 commit：runtime cleanup / compatibility stabilization / transport schema convergence）。
2. 跑一次最终回归快照（`tests/unit` + `tests/integration`）。
3. 合并回主线或发 PR，并在 plan/README 记录 sign-off commit。
