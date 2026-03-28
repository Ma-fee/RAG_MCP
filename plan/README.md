# RAG MCP v1 分阶段实施总计划

来源 RFC: `docs/rfcs/draft/RFC-0001-rag-mcp-v1-architecture.md`

## 执行规则（强制）

- [ ] 每次只允许实现一个 Phase；未签收不得进入下一个 Phase。
- [ ] 开发前必须先完成当前 Phase 文档中的“Plan Review”勾选。
- [ ] 每个 Task 必须按 TDD 循环执行：先测失败 -> 最小实现 -> 测试通过 -> 记录提交。
- [ ] 每完成一个 Step / Task 立即打勾，保留执行记忆。
- [ ] Phase 验收命令全部通过后，填写签收区并冻结该 Phase。

## Phase 看板

- [x] Phase 1: Keyword + Stdio 可用基线（可运行、可检索、可溯源）  
文档: `plan/phase-1-keyword-stdio-mvp.md`
- [x] Phase 2: Vector + Chroma + Embedding 配置一致性  
文档: `plan/phase-2-vector-chroma.md`
- [x] Phase 3: Docling/PDF + 结构化分块 + 非文本挂接  
文档: `plan/phase-3-docling-structure.md`
- [x] Phase 4: HTTP 传输对等 + 安全约束 + 发布验收  
文档: `plan/phase-4-http-parity-release.md`

## 里程碑签收标准

- Phase 1 签收：`rag_rebuild_index`、`rag_index_status`、`rag_search(keyword)`、`rag://` 读取全链路可用（stdio）。
- Phase 2 签收：`vector` 模式可用，`keyword` 与 `vector` 共用同一 URI 体系，配置不一致报错语义正确。
- Phase 3 签收：Docling 统一文档模型落地，结构上下文字段完整，表格/图片按 RFC 规则挂接且不破坏 URI 稳定性。
- Phase 4 签收：HTTP 与 stdio 行为一致，错误模型一致，文档与验收脚本完备，可作为 v1 候选版本。
