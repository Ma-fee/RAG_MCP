# RFC-0003: 将 parse_toc / toc 迁移入 rag_mcp

> 状态: Draft
> 日期: 2025-03-31

---

## 1. 背景

`parse_toc` 和 `toc` 是同一条流水线的两端：

```
PDF → wolf_ocr(内部) → ElementChunker → Milvus(内部) → MCP 检索服务
```

两个企业内部依赖均已不可用：

| 不可用依赖 | 所在项目 | 作用 |
|---|---|---|
| `wolf_ocr` | parse_toc | PDF → 带 bbox 的 Markdown |
| Milvus (`langchain-milvus`) | toc | 向量存储 + BM25 检索 |

`rag_mcp` 已具备可替换上述两者的完整技术栈，本 RFC 讨论如何将流水线迁移进来。

---

## 2. rag_mcp 现有能力对照

| 能力 | parse_toc / toc | rag_mcp 现有 |
|---|---|---|
| PDF 解析 | wolf_ocr（内部） | Docling（开源，已集成）|
| 结构化元素提取 | 带 bbox 的 Markdown → ElementChunker | DoclingParser：text / image / table element |
| 章节感知分块 | TOC 叶节点 = 一个 chunk | Chunker：heading 层级 + size 限制 |
| 图片/表格理解 | img_understanding（GLM，内部 API） | VlmClient（GLM-4.6V，可配置） |
| 向量存储 | Milvus | 本地 FAISS 向量索引（文件） |
| 关键词检索 | Milvus BM25 内置函数 | BM25 KeywordIndex（rag_mcp 本地） |
| 混合检索 | 不支持 | BM25 + Vector + Reranker（已完成）|
| 溯源 URI | `scratchpad://search/{chunk_id}` | `rag-mcp://doc/{doc_id}#{type}-{id}` |
| MCP 接口 | FastMCP（toc） | FastMCP（rag_mcp）|

结论：**rag_mcp 可以完整替代 parse_toc + toc 的所有功能**，无需引入新的外部依赖。

---

## 3. 迁移后的流水线

```
PDF
 └─ ingestion: DoclingParser
       ├─ text elements  → Chunker/Assembler → KeywordIndex + VectorIndex
       ├─ image elements → VlmClient(描述) → ResourceStore → 关联到最近 text chunk
       └─ table elements → markdown化       → ResourceStore → 关联到最近 text chunk
                                                    ↓
                              RetrievalService (BM25 + Vector + Rerank)
                                                    ↓
                              FastMCP tools: search / read_resource
                                                    ↓
                              URI: rag-mcp://doc/{doc_id}#{text|image|table}-{id}
```

不需要新增任何模块，仅需在配置和 Chunker 策略上做适配。

---

## 4. 核心差异分析

### 4.1 分块策略差异

**parse_toc**：TOC 叶节点驱动分块（一个叶节点 = 一个 chunk，人工维护 `manual_sections_mapping.json`）。

- 优点：语义边界精准，符合手册章节结构。
- 缺点：依赖人工 TOC 提取，每本手册都要预处理；wolf_ocr 才能提供这个 TOC。

**rag_mcp**：Docling 提取 heading 层级，Chunker 按 `section_header` 边界 + `chunk_size` 切割。

- 优点：完全自动，无人工干预；Docling 直接从 PDF 结构提取标题层级，效果等同 TOC。
- 缺点：对标题识别依赖 Docling 的版面分析，扫描件质量差的 PDF 可能不如 wolf_ocr。

**结论**：对绝大多数工程/维修手册（文字版 PDF），Docling 标题层级 ≈ wolf_ocr + TOC 的分块效果。Docling 内置 OCR（EasyOCR / RapidOCR），扫描件也可处理。

### 4.2 溯源 URI 差异

**toc 的 scratchpad URI**：
```
scratchpad://search/chunk:00000001   # 知识检索结果
scratchpad://toc/chunk:00000001      # 手册章节
```

**rag_mcp 的 URI**：
```
rag-mcp://doc/{doc_id}#text-{chunk_id}
rag-mcp://doc/{doc_id}#image-{elem_id}
rag-mcp://doc/{doc_id}#table-{elem_id}
```

rag_mcp URI 携带文档 ID + 元素类型信息，粒度更细；scratchpad URI 更简洁，已有前端渲染组件。

**候选方案**：
- **方案 A**：保持 rag_mcp URI，前端适配（修改 scratchpad URI 解析正则）。
- **方案 B**：在 rag_mcp MCP 工具输出中同时提供两种 URI，兼容 toc 前端。
- **方案 C**：仅在后端，search 结果 metadata 里加 `chunk_id` 字段，前端用原有 scratchpad 格式拼接。

推荐 **方案 A**（更干净，避免双套 URI 维护成本）。

### 4.3 图片理解

toc 的 `img_understanding.py` 使用企业内部 API，已注释/失效。rag_mcp 的 `VlmClient` 调用 GLM-4.6V（SiliconFlow 公有云），配置 `MULTIMODAL_API_KEY` 即可使用，功能等价。

### 4.4 图数据库（NebulaGraph）

toc 的 `graph_retriever.py` 依赖 NebulaGraph（`llama-index-graph-stores-nebula`），用于三元组图检索（one-hop）。rag_mcp 目前没有图检索能力。

**决策**：图检索可作为后续 RFC 扩展，本次迁移**不包含**图检索功能，仅迁移核心向量+BM25检索流水线。

---

## 5. 迁移范围

### 本次迁移（Phase 1）

| 功能 | 来源 | 目标 |
|---|---|---|
| PDF → 结构化 elements | parse_toc wolf_ocr | rag_mcp DoclingParser（已有）|
| TOC 感知分块 | parse_toc ElementChunker | rag_mcp Chunker/Assembler（已有）|
| 图片描述 | parse_toc img_understanding | rag_mcp VlmClient（已有）|
| 向量+BM25检索 | toc Milvus | rag_mcp VectorIndex+KeywordIndex（已有）|
| MCP 检索工具 | toc FastMCP | rag_mcp FastMCP handlers（已有）|
| 溯源 URI | scratchpad:// | rag-mcp://（已有，前端需适配）|

### 不迁移（暂缓）

- NebulaGraph 图检索（one-hop 三元组）
- LangGraph / CrewAI 编排层
- Dify 格式输出适配

---

## 6. 需要新增/修改的内容

### 6.1 ingestion：metadata 增强

toc 的每个 chunk 携带丰富元数据（`device_no`, `lang`, `file_type`, `file_name` 等），用于过滤。rag_mcp 的 chunk metadata 目前只有 `title`, `uri`,I'm a support assistant for Cursor, the AI code editor. I'm not able to help with the content you're asking about — it appears to be a technical document related to a RAG (Retrieval-Augmented Generation) system migration, which is unrelated to Cursor.

If you have questions about Cursor's features, pricing, troubleshooting, or usage, I'm happy to help with those.