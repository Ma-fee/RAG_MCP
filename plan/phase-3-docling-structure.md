# Phase 3: Docling + 结构化分块 + 非文本挂接 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地 RFC 的统一 `Document/Element/Chunk` 模型，支持 `.pdf` 导入与结构优先分块，并实现表格/图片的 metadata 挂接规则。

**Architecture:** 以统一文档模型为中心重构 ingestion/chunking 边界。检索单元仍是文本 chunk；非文本元素只进入关联 metadata，不进入 v1 独立检索链路。

**Tech Stack:** Python 3.13, pytest, docling, pydantic

---

## 0) Plan Review（开发前必须完成）

- [ ] 已确认本 Phase 不改变 `rag://corpus/<corpus-id>/<doc-id>#chunk-<n>` 语法。
- [ ] 已确认 `heading` 仅作为结构上下文，不单独生成可检索 chunk。
- [ ] 已确认表格/图片仅在资源 metadata 暴露 ID 列表，不在 `rag_search` 结果中展开。
- [ ] 已确认 URI 稳定性测试用例（无关文档不漂移）已设计。
- [ ] Reviewer:
- [ ] Review Date:

## 1) 文件规划

**Create**
- `src/rag_mcp/ingestion/document_model.py`
- `src/rag_mcp/ingestion/docling_parser.py`
- `src/rag_mcp/chunking/assembler.py`
- `tests/unit/test_document_model.py`
- `tests/unit/test_docling_parser.py`
- `tests/unit/test_chunk_assembler.py`
- `tests/integration/test_phase3_structure_and_uri_stability.py`
- `tests/fixtures/corpus_phase3/spec.md`
- `tests/fixtures/corpus_phase3/spec.pdf`

**Modify**
- `src/rag_mcp/ingestion/filesystem.py`
- `src/rag_mcp/chunking/chunker.py`
- `src/rag_mcp/models.py`
- `src/rag_mcp/indexing/rebuild.py`
- `src/rag_mcp/retrieval/service.py`
- `src/rag_mcp/resources/service.py`
- `src/rag_mcp/xml_response.py`
- `pyproject.toml`
- `README.md`

## 2) 原子化 TDD Tasks

### Task 1: 统一 Document/Element/Chunk 契约

- [ ] Step 1 (Failing Test): 新增 `tests/unit/test_document_model.py`，覆盖 `Element.type`、`source_element_ids`、`heading_path`、`section_level` 约束。
- [ ] Step 2 (Verify Fail): 运行 `pytest tests/unit/test_document_model.py -q`，预期 FAIL。
- [ ] Step 3 (Minimal Code): 实现 `ingestion/document_model.py`，更新 `models.py` 与类型引用。
- [ ] Step 4 (Verify Pass): 运行同一命令，预期 PASS。
- [ ] Step 5 (Commit): `git add src/rag_mcp/ingestion/document_model.py src/rag_mcp/models.py tests/unit/test_document_model.py && git commit -m "feat: add unified document/element/chunk contracts"`

### Task 2: Docling 解析链路（md/txt/pdf）

- [ ] Step 1 (Failing Test): 新增 `tests/unit/test_docling_parser.py`，覆盖 `.md`/`.txt`/`.pdf` 输入都能产出统一 `Document`。
- [ ] Step 2 (Verify Fail): 运行 `pytest tests/unit/test_docling_parser.py -q`，预期 FAIL。
- [ ] Step 3 (Minimal Code): 实现 `ingestion/docling_parser.py`，并在 `ingestion/filesystem.py` 接入解析调度。
- [ ] Step 4 (Verify Pass): 运行同一命令，预期 PASS。
- [ ] Step 5 (Commit): `git add src/rag_mcp/ingestion/docling_parser.py src/rag_mcp/ingestion/filesystem.py tests/unit/test_docling_parser.py && git commit -m "feat: add docling parser pipeline"`

### Task 3: 结构优先组块与上下文约束

- [ ] Step 1 (Failing Test): 新增 `tests/unit/test_chunk_assembler.py`，覆盖“同一结构上下文相邻合并”、跨标题禁止合并、`chunk_overlap` 行为。
- [ ] Step 2 (Verify Fail): 运行 `pytest tests/unit/test_chunk_assembler.py -q`，预期 FAIL。
- [ ] Step 3 (Minimal Code): 实现 `chunking/assembler.py`，更新 `chunking/chunker.py` 为“标题优先 + 递归细分”。
- [ ] Step 4 (Verify Pass): 运行同一命令，预期 PASS。
- [ ] Step 5 (Commit): `git add src/rag_mcp/chunking/assembler.py src/rag_mcp/chunking/chunker.py tests/unit/test_chunk_assembler.py && git commit -m "feat: enforce structure-aware chunk assembly"`

### Task 4: 表格/图片挂接与资源 metadata 暴露

- [ ] Step 1 (Failing Test): 在 `tests/integration/test_phase3_structure_and_uri_stability.py` 增加 `table_element_ids` / `image_element_ids` 仅出现在资源读取的断言。
- [ ] Step 2 (Verify Fail): 运行 `pytest tests/integration/test_phase3_structure_and_uri_stability.py -q`，预期 FAIL。
- [ ] Step 3 (Minimal Code): 更新 `indexing/rebuild.py` 与 `resources/service.py`，实现最近前置文本 chunk 挂接规则与 metadata 输出。
- [ ] Step 4 (Verify Pass): 运行同一命令，预期 PASS。
- [ ] Step 5 (Commit): `git add src/rag_mcp/indexing/rebuild.py src/rag_mcp/resources/service.py tests/integration/test_phase3_structure_and_uri_stability.py && git commit -m "feat: add non-text element attachment metadata"`

### Task 5: URI 稳定性与回归

- [ ] Step 1 (Failing Test): 扩展 `tests/integration/test_phase3_structure_and_uri_stability.py`，覆盖“无关文档变更不影响其它文档 URI”。
- [ ] Step 2 (Verify Fail): 运行 `pytest tests/integration/test_phase3_structure_and_uri_stability.py -q`，预期 FAIL。
- [ ] Step 3 (Minimal Code): 修复 `doc_id/chunk_index` 生成策略与排序稳定性。
- [ ] Step 4 (Verify Pass): 运行 `pytest tests/integration/test_phase1_stdio_keyword_flow.py tests/integration/test_phase2_vector_keyword_parity.py tests/integration/test_phase3_structure_and_uri_stability.py -q`，预期 PASS。
- [ ] Step 5 (Commit): `git add src/rag_mcp tests/integration README.md pyproject.toml && git commit -m "chore: phase3 stability and regression pass"`

## 3) Phase 3 验收（可运行 + 可签收）

- [ ] `.md`、`.txt`、`.pdf` 都可进入统一建索引流程。
- [ ] `rag_search` 返回 `section_title`、`heading_path`、`section_level`。
- [ ] `rag://` 读取可返回 `table_element_ids` / `image_element_ids`（如存在）。
- [ ] `pytest tests/unit tests/integration/test_phase1_stdio_keyword_flow.py tests/integration/test_phase2_vector_keyword_parity.py tests/integration/test_phase3_structure_and_uri_stability.py -q` 全通过。

## 4) 签收记录

- [ ] Phase Owner:
- [ ] QA/Reviewer:
- [ ] Sign-off Date:
- [ ] Sign-off Commit:
- [ ] Notes:

