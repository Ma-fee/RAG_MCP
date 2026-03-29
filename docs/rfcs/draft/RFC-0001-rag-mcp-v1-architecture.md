---
rfc_id: RFC-0001
title: RAG MCP v1 架构设计
status: DRAFT
author: admin
reviewers: []
created: 2026-03-28
last_updated: 2026-03-28
decision_date:
related_prds: []
related_rfcs: []
---

# RFC-0001: RAG MCP v1 架构设计

## 概述

本 RFC 提议为 `rag-mcp` 建立第一版架构：一个基于 Python 的 Model Context Protocol（MCP）服务，负责索引本地文档目录，并向 MCP 客户端暴露检索工具与可读取资源，而不是在服务内部直接生成最终答案。

当前目标是定义一个足够小、可以尽快交付的 v1，同时保证整体结构能够支撑后续扩展。预期结果是一个单进程服务，同时支持 `stdio` 与 HTTP 两种传输方式，能够按目录触发索引重建、本地持久化向量数据，并通过 `rag://corpus/<corpus-id>/<doc-id>#chunk-<n>` 形式的资源 URI 为上层 LLM 提供可引用、可回读的知识来源。

## 目录

- [背景与上下文](#背景与上下文)
- [问题陈述](#问题陈述)
- [目标与非目标](#目标与非目标)
- [评估标准](#评估标准)
- [方案分析](#方案分析)
- [推荐方案](#推荐方案)
- [技术设计](#技术设计)
- [安全性考虑](#安全性考虑)
- [实施计划](#实施计划)
- [开放问题](#开放问题)
- [决策记录](#决策记录)
- [参考资料](#参考资料)

---

## 背景与上下文

### 当前状态

当前仓库仍然是一个最小 Python 骨架，仅包含 `main.py` 与 `pyproject.toml`。仓库中尚未实现文档解析、向量索引、MCP 服务接入、检索逻辑、资源读取、测试或运行说明。

### 历史背景

这是仓库中的第一份架构 RFC。它的作用是为后续实现提供规范驱动的基线，避免在编码阶段临时决定关键行为，导致接口、索引生命周期和运行方式出现偏差。

### 术语表

| Term | Definition |
|------|------------|
| RAG | Retrieval-Augmented Generation，先检索上下文再由上层模型结合结果生成答案 |
| MCP | Model Context Protocol，用于向兼容客户端暴露工具能力 |
| Corpus | 被索引的一组源文档目录 |
| Chunk | 从源文档切分出的较小文本片段，用于嵌入与检索 |
| Active Index | 当前被服务使用的持久化索引 |
| Resource URI | 服务暴露的稳定资源标识，v1 中采用 `rag://` 命名空间 |

---

## 问题陈述

### 当前问题

仓库需要一份明确的 v1 架构规范，用于约束一个可通过 MCP 调用的 retrieval-first RAG 服务。若没有书面规范，传输层设计、索引重建策略、资源命名方式、检索工具契约等关键问题会在实现中被临时决定，增加返工风险。

### 证据

- 当前仓库没有任何现成的 RAG 或 MCP 实现。
- 当前产品形态已经明确为 MCP 服务，而不是前端应用或独立聊天程序。
- 项目同时涉及文档导入、索引、检索、资源读取和双传输支持，多个决策彼此耦合。

### 不处理的影响

- Cost: 编码阶段会不断回头重做技术决策，拖慢交付速度。
- Risk: 索引行为、查询行为和对外接口可能出现不一致假设。
- Opportunity: 在没有明确接口和生命周期定义前，项目无法成为可复用的知识型 MCP 服务。

---

## 目标与非目标

### 目标（范围内）

1. 定义一个 Python 优先的本地文档 RAG MCP 服务 v1 架构。
2. 支持从指定目录构建索引，并在每次重建时执行全量重建。
3. 同时通过 `stdio` 与 HTTP 暴露检索工具与 `rag://` 资源读取能力。
4. 本地持久化向量与来源元数据，使服务重启后仍可继续使用活动索引。
5. 通过环境变量接入 OpenAI 兼容接口，用于 embedding 生成。
6. 使上层 LLM 能够基于检索结果回答，并在回答中使用 `[](rag://...)` 进行资源溯源。

### 非目标（范围外）

1. 增量索引、文件监听或按变更同步。
2. v1 中的多租户或多语料并行服务。
3. Web 前端或终端聊天界面。
4. 服务内置的最终答案生成主路径。
5. 混合检索、重排、复杂查询规划等高级检索能力。
6. 面向生产托管场景的完整鉴权、限流与租户隔离。

### 成功标准

- [ ] 客户端可以基于本地目录路径重建索引。
- [ ] 客户端可以搜索当前活动索引，并获得带分数的来源片段。
- [ ] 搜索结果返回稳定的 `rag://` URI，且对应资源可被再次读取。
- [ ] 上层 LLM 可以基于检索结果组织回答，并使用 `[](rag://...)` 完成资源溯源。
- [ ] `stdio` 与 HTTP 模式下暴露相同的核心工具行为。
- [ ] 常见错误场景能够返回明确且可操作的错误信息。

---

## 评估标准

用于评估 v1 架构方案的标准如下：

| Criterion | Weight | Description | Minimum Threshold |
|-----------|--------|-------------|-------------------|
| Time to Value | High | 多快能交付一个可用的 v1 | 能在单个小周期内完成 |
| Maintainability | High | 代码是否容易理解、维护和扩展 | 具有清晰模块边界 |
| MCP Compatibility | High | 是否适配本地 MCP 客户端与远程 HTTP 用法 | 同时支持两种传输 |
| Operational Simplicity | High | 部署、运行、排障成本是否足够低 | 满足本地优先开发 |
| Flexibility | Medium | 是否保留后续扩展空间 | 不阻断 post-v1 演进 |

---

## 方案分析

### 方案 1：单进程统一 Python 服务

**说明**

使用一个 Python 进程承载文档导入、索引、检索、资源读取以及两种 MCP 传输方式。`stdio` 与 HTTP 通过共享内部服务层完成能力复用。

**优点**

- 对 v1 来说实现成本最低，适合当前仓库从零起步的状态。
- 索引与查询在一个服务内完成，减少跨服务协调成本。
- 传输层可以保持很薄，核心逻辑只实现一次。

**缺点**

- 相比拆分式架构，服务边界没有那么显式。
- HTTP 与 `stdio` 的运行关注点会落在同一个部署单元内。
- 无法分别扩展索引与查询执行能力。

**按标准评估**

| Criterion | Rating | Notes |
|-----------|--------|-------|
| Time to Value | 5 | 最少的初始构建复杂度 |
| Maintainability | 4 | 只要内部模块边界清晰，仍可维护 |
| MCP Compatibility | 5 | 直接满足双传输需求 |
| Operational Simplicity | 5 | 单服务、本地优先、便于调试 |
| Flexibility | 4 | 未来仍可从内部模块中提取独立层 |

**工作量估算**

- Complexity: Medium
- Resources: 1 名工程师，1-2 周形成可用 v1
- Dependencies: FastMCP 或官方 Python MCP SDK、Chroma、PDF/文本解析、embedding API

**风险评估**

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| 传输层逻辑侵入核心逻辑 | Medium | Medium | 保持 transport adapter 足够薄 |
| 大目录全量重建时阻塞查询 | Medium | Medium | v1 限定目标规模并明确文档说明 |

---

### 方案 2：共享 RAG Core + 分离 `stdio`/HTTP 入口

**说明**

先构建内部共享的 RAG Core，再分别为本地 `stdio` MCP 与远程 HTTP 暴露两个轻量入口层。

**优点**

- 协议接入与领域逻辑分层更清晰。
- 后续可以更容易独立演进不同传输模式。
- 核心层被传输细节污染的风险更低。

**缺点**

- 在 v1 阶段需要更早引入抽象，增加前期结构成本。
- 入口、打包与启动方式会更复杂。
- 当前仓库规模较小时，容易出现过度设计。

**按标准评估**

| Criterion | Rating | Notes |
|-----------|--------|-------|
| Time to Value | 4 | 仍可行，但前期结构设计更多 |
| Maintainability | 5 | 内部边界最清晰 |
| MCP Compatibility | 5 | 同样可以很好支持双传输 |
| Operational Simplicity | 4 | 启动路径和组织稍复杂 |
| Flexibility | 5 | 对未来演进最友好 |

**工作量估算**

- Complexity: Medium
- Resources: 1 名工程师，1-2 周
- Dependencies: 与 Option 1 相同

**风险评估**

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| 抽象过早导致交付放缓 | Medium | Medium | 限制 core 接口数量，避免泛化 |
| 两种入口行为逐渐漂移 | Low | Medium | 通过共享服务测试约束一致性 |

---

### 方案 3：检索服务与生成服务拆分

**说明**

将检索与索引能力、资源读取能力拆分为不同服务或进程，各自承担独立职责。

**优点**

- 长期看最利于独立扩容与职责隔离。
- 检索能力可以被上层 LLM 或非生成型消费者单独复用。
- 更适合未来复杂托管形态。

**缺点**

- 对当前 v1 来说实现与运维成本最高。
- 在实际规模尚未出现前就引入服务边界，收益不足。
- 错误处理、部署和排障复杂度显著提高。

**按标准评估**

| Criterion | Rating | Notes |
|-----------|--------|-------|
| Time to Value | 2 | 当前阶段过重 |
| Maintainability | 3 | 边界清晰，但系统更碎片化 |
| MCP Compatibility | 4 | 可以实现，但协调成本更高 |
| Operational Simplicity | 2 | 本地开发与调试成本最高 |
| Flexibility | 5 | 长期扩展性强，但 v1 不需要 |

**工作量估算**

- Complexity: High
- Resources: 1-2 名工程师，2-4 周
- Dependencies: 除基础依赖外还需处理服务间协作

**风险评估**

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| 架构超出 v1 实际需求 | High | High | 不作为首版方案 |
| 跨服务调试拖慢验证速度 | Medium | High | 等规模或团队复杂度提升后再考虑 |

---

### 方案对比汇总

| Criterion | Option 1 | Option 2 | Option 3 |
|-----------|----------|----------|----------|
| Time to Value | 5 | 4 | 2 |
| Maintainability | 4 | 5 | 3 |
| MCP Compatibility | 5 | 5 | 4 |
| Operational Simplicity | 5 | 4 | 2 |
| Flexibility | 4 | 5 | 5 |
| **Overall** | **4.6** | **4.6** | **3.2** |

---

## 推荐方案

### 推荐选项

**Option 1: 单进程统一 Python 服务**

### 推荐理由

Option 1 与 Option 2 都满足当前需求，但在当前仓库仍然极简、且首要目标是尽快得到可用 retrieval-first MCP 服务的前提下，Option 1 更符合实际约束。该方案可以在不提前拆服务的情况下快速交付，同时通过清晰的内部模块边界保留后续演进空间。

### 接受的权衡

1. 部署边界不如拆分方案清晰：这是可接受的，因为 v1 主要服务本地优先的单项目场景。
2. 传输逻辑侵入核心层的风险更高：这是可接受的，前提是实现阶段严格保持 transport adapter 简洁。

### 约束条件

- 尽管部署为单进程，内部仍必须拆分为清晰的配置、索引、检索、资源、传输模块。
- post-v1 演进路线只能作为后续方向记录，不能混入 v1 必选需求。

---

## 技术设计

### 架构概览

v1 只维护一个活动索引。客户端通过目录路径发起重建请求后，服务扫描支持的文件类型，抽取文本、切分 chunk、生成 embedding、写入本地持久化向量库，并将该目录对应索引标记为活动索引，供后续检索与资源读取调用。

```text
┌──────────────┐
│ MCP Client   │
└──────┬───────┘
       │
 ┌─────┴─────────────┐
 │ stdio / HTTP MCP  │
 └─────┬─────────────┘
       │
 ┌─────┴───────────────────────────────┐
 │ RAG Service Core                    │
 │ - config                            │
 │ - index manager                     │
 │ - retrieval service                 │
 │ - resource service                  │
 └─────┬───────────────────────────────┘
       │
 ┌─────┼─────────────┬─────────────────┐
 │ file loader       │ embedding API   │
 │ chunker           │                 │
 │ metadata builder  │                 │
 └─────┬─────────────┴─────────────────┘
       │
 ┌─────┴─────────────┐
 │ Chroma 持久化存储 │
 │ + source metadata │
 └───────────────────┘
```

### 对外工具与资源接口

服务对外暴露三个 MCP 工具与一组 `rag://` MCP Resources：

- `rag_rebuild_index(directory_path)`: 基于指定目录重建活动索引。
- `rag_index_status()`: 返回活动索引是否存在以及当前语料摘要信息。
- `rag_search(query, mode, top_k=5)`: 按指定检索模式返回最相关的 chunk、分数、资源 URI 和来源元数据。
- `rag://...` resources: 允许客户端根据检索结果中的 URI 读取对应 chunk 内容及其元数据。

检索工具应使用结构化返回，并包含足够的上下文，便于上层 LLM 直接组织答案。每条命中结果至少包含以下字段：

- `text`
- `title`
- `uri`
- `score`
- `metadata`

`rag_search` 在架构上定义以下检索模式：

- 当前版本实现：
  - `vector`
  - `keyword`
- 当前版本预留但未实现：
  - `hybrid`
  - `rerank`

### 检索模式与检索流水线

v1 采用“单查询接口，多检索模式”的设计。不同模式共享同一套文档标准化、`corpus_id`、`doc_id`、`chunk_index` 和 `rag://` 资源命名规则，避免不同检索方式返回不同资源标识。

当前版本实际落地的模式如下：

- `vector`
  - 对查询生成 embedding
  - 使用 Chroma 持久化向量索引执行相似度检索
  - 返回 top-k chunk
- `keyword`
  - 基于 BM25 / 倒排索引执行关键词检索
  - 返回 top-k chunk

当前版本明确预留但暂不实现的模式如下：

- `hybrid`
  - 预留为向量召回与关键词召回并行执行
  - 预留融合、去重和统一排序步骤
- `rerank`
  - 预留为候选集合召回后再进行重排
  - 可由模型或规则型 reranker 承担排序职责

设计约束如下：

- `vector` 与 `keyword` 必须共享相同的 chunk 粒度。
- 不同模式返回的 `uri` 必须引用同一批底层 chunk 资源。
- `score` 仅保证在同一次调用、同一模式内部可排序，不承诺跨模式可比较。
- 后续增加 `hybrid` 与 `rerank` 时，不改变 `rag_search` 根接口、不改变 XML envelope、不改变 `rag://` 语法。

### 分块策略与结构保留

当前版本采用“TOC/标题层级优先 + 过长再递归细分”的默认分块策略。

具体规则如下：

- 对 Markdown 或具备清晰标题结构的文档：
  - 优先按标题层级切分逻辑章节。
  - 每个章节先作为结构化分块候选。
  - 若章节长度超过目标阈值，则在章节内部继续递归细分为多个最终检索子块。
- 对 TXT、PDF 或无法稳定识别标题结构的文档：
  - 直接回退到通用递归分块。

该策略的目标是同时满足以下要求：

- 尽量保留文档结构语义。
- 让 `vector` 与 `keyword` 共用同一套最终子块。
- 保持 `rag://corpus/<corpus-id>/<doc-id>#chunk-<n>` 指向稳定、可解释的检索单元。

v1 不实现独立的父块资源，也不实现 parent-child 检索；但在架构上为其预留扩展位。未来若升级到 parent-child 模式：

- 父块可对应 TOC 章节。
- 子块继续作为检索单元。
- 检索命中子块，展示或汇总时可回溯到父块。

### 检索结果 XML 结构

`rag_search` 的每条结果在 v1 中应满足以下结构约束：

```json
{
  "text": "chunk content",
  "title": "document title",
  "uri": "rag://corpus/<corpus-id>/<doc-id>#chunk-<n>",
  "score": 0.0,
  "metadata": {
    "corpus_id": "<hash>",
    "doc_id": "<stable-doc-id>",
    "chunk_index": 0,
    "file_type": "md|txt|pdf",
    "title": "document title",
    "section_title": "技术设计",
    "heading_path": "RFC-0001 > 技术设计 > 检索模式与检索流水线",
    "section_level": 2,
    "relative_path": "docs/example.md",
    "chunk_length": 512,
    "indexed_at": "2026-03-28T18:00:00Z"
  }
}
```

其中：

- `corpus_id` 由规范化目录路径计算 hash 得到。
- `doc_id` 由文档相对路径生成稳定 hash，内容变化不影响 `doc_id`，路径变化会导致 `doc_id` 变化；该字段不追求人类可读性，优先保证 URI 稳定且不泄露本地路径。
- `score` 保持为可排序数值，不在 v1 中承诺具体分值范围语义。
- `metadata` 采用中等粒度策略，满足调试、排序分析和溯源需要，但不暴露本地绝对路径。
- 若源文档具备标题结构，`metadata` 应补充结构上下文字段：
  - `section_title`
  - `heading_path`
  - `section_level`
- `corpus_id + doc_id + chunk_index` 构成唯一的稳定寻址字段，其他结构上下文字段仅用于展示上下文。

`rag_search` 额外返回 `mode` 字段，用于表明本次命中的检索模式。`heading_path` 是展示优先的标题链路文本（例如“文档 > 章节 > 小节”），不参与 `rag://` 寻址；标题变化可以更新 `heading_path`，但不应影响 `doc_id`。

### 资源 URI 规范

v1 中 `rag://` 采用如下稳定语法：

`rag://corpus/<corpus-id>/<doc-id>#chunk-<n>`

字段约定如下：

- `<corpus-id>`: 基于规范化目录路径生成的 hash，用于保证同一路径重建后 URI 稳定。
- `<doc-id>`: 基于被索引目录下的文档相对路径生成稳定 hash，内容变化不影响 `doc_id`，路径变化会导致 `doc_id` 改变；该字段不追求人类可读性，优先保证 URI 稳定与不泄露本地绝对路径。
- `<n>`: chunk 在文档内的顺序编号，从 `0` 开始。

该 URI 既用于回答中的资源溯源，也必须可被 MCP Resource 读取。v1 不引入内容版本号；若目录内容变化但路径不变，`corpus-id` 保持不变，具体 chunk 内容随重建更新。

### 索引生命周期

- v1 只支持全量重建索引。
- 每次 `rag_rebuild_index` 调用都会替换掉之前的活动索引。
- 重建过程必须先在临时目录完成，成功后再一次性切换活动索引。
- 若重建失败，旧活动索引必须继续保持可读，不得因为半成品索引导致服务进入不可用状态。
- v1 支持的本地文件类型为 `.md`、`.txt` 和 `.pdf`。
- 检索结果中的 `uri` 必须稳定可复现，并可被 MCP Resource 再次读取。
- 当没有活动索引时，检索与资源读取接口应返回明确错误。
- 同一路径重复重建时，`corpus_id` 必须保持不变。
- 向量索引与关键词索引必须在同一次重建流程中同步更新，避免不同模式读取到不同版本的索引数据。
- 最终可检索子块必须是 `rag://` URI 指向的唯一资源单元。
- 文档结构发生变化时，仅允许受影响文档的 `chunk_index` 发生变化，不应导致无关文档的 URI 漂移。

### 存储与配置

- 向量数据与来源元数据存储在本地持久化目录中。
- 默认向量存储采用 `Chroma` 持久化，默认持久化位置应放在仓库本地数据目录下。
- `Chroma` 负责向量索引目录的持久化；服务层还必须维护独立 manifest，用于记录活动索引与校验元数据。
- 活动索引默认通过 `active_index.json` 指向当前版本，而不是依赖符号链接。
- `active_index.json` 至少应记录：`corpus_id`、当前索引目录、`indexed_at`、`embedding_model` 与 embedding 维度。
- v1 只保留当前活动索引版本；新版本切换成功后应清理旧版本目录，不保留 previous 或全部历史版本。
- MCP 接入默认采用 `FastMCP` 或官方 Python SDK。
- `stdio` 为默认本地运行模式；HTTP 仅在显式启动参数或独立启动命令下启用。
- RFC 保留 `EmbeddingProvider` 抽象接口，但 v1 只实现 `OpenAI-compatible` provider。
- 模型接入通过 OpenAI 兼容环境变量配置：
  - `OPENAI_BASE_URL`
  - `OPENAI_API_KEY`
  - `EMBEDDING_MODEL`
- 资源 URI 默认使用 `rag://` 命名空间，不以本地绝对路径作为公共接口。

### 技术选型与比较

当前版本采用“协议层复用开源官方能力，RAG 编排层自定义实现，底层存储与算法复用成熟库”的技术路线。这样可以在不牺牲 RFC 中既定契约的前提下，控制实现复杂度。

#### 1. MCP 服务层

| 选项 | 结论 | 原因 |
|------|------|------|
| FastMCP / 官方 Python SDK | 采用 | 与 MCP 协议贴合度最高，能直接承载 tools、resources、`stdio` 与 HTTP，两种传输方式都能落地 |
| 自行实现 MCP 协议层 | 不采用 | 自由度高，但会把大量精力消耗在协议细节而不是 RFC 核心能力上 |
| 其它非官方封装 | 不采用 | 稳定性、兼容性和后续维护成本不如官方路径明确 |

结论：MCP 层采用开源官方 SDK，而不是自定义协议框架。

#### 2. RAG 编排层

| 选项 | 结论 | 原因 |
|------|------|------|
| 自定义编排层 | 采用 | RFC 已定义 `rag://` 资源、XML-first 契约、`corpus_id + doc_id + chunk_index` 寻址、TOC 优先分块，使用自定义编排更容易保持这些约束 |
| LlamaIndex 作为主框架 | 不采用为主框架 | 检索能力丰富，但会带入自身 node/index 抽象，容易反向约束当前 RFC 的 URI 和 metadata 契约 |
| Haystack 作为主框架 | 不采用为主框架 | pipeline 能力强，但框架层较重，对当前 v1 的协议自定义不够轻量 |

结论：RAG 编排层自定义实现，避免主框架绑死资源模型与返回契约。

#### 3. 向量检索

| 选项 | 结论 | 原因 |
|------|------|------|
| Chroma | 采用 | 本地持久化简单，Python 集成成本低，适合单机 v1 |
| FAISS + 自建持久化 | 不作为首选 | 检索性能可控，但持久化、metadata 管理和工程工作量更高 |
| SQLite 向量扩展 | 不作为首选 | 可行，但当前生态成熟度与开发效率不如 Chroma 直接 |

结论：向量检索采用 Chroma，保持本地优先与低运维。Chroma 负责向量数据持久化，服务层通过独立 manifest 记录 `embedding_model`、embedding 维度、`corpus_id` 和活动索引目录等校验信息。RFC 保留 `EmbeddingProvider` 抽象接口，但 v1 仅落地 `OpenAI-compatible` provider。

#### 4. 关键词检索

| 选项 | 结论 | 原因 |
|------|------|------|
| BM25 / 倒排索引 | 采用 | 是标准关键词检索路径，也最适合未来扩展到 hybrid |
| 向量库元数据过滤近似替代 | 不采用 | 不能替代真正关键词检索，对精确词、专有名词和文件名场景不可靠 |
| SQLite FTS 作为主方案 | 暂不采用 | 能力强，但会引入另一套存储中心和额外同步复杂度 |

结论：关键词检索采用 BM25 / 倒排索引；具体库可在实现阶段从 `bm25s` 或 `rank-bm25` 这类底层库中选择。

#### 5. 文档解析与结构提取

| 选项 | 结论 | 原因 |
|------|------|------|
| Docling 主导的统一文档处理层 | 采用 | 更适合统一提取文本、标题、表格、图片等元素，并为多模态理解预留统一文档表示 |
| Unstructured 主导的元素抽取层 | 备选 | 元素化抽取成熟，但在统一文档表示和多模态预留上不如 Docling 更贴合当前架构 |
| Markdown 原生结构解析 + TXT 纯文本 + PDF 文本抽取 | 不作为主方案 | 可满足基础文本抽取，但对表格、图片、元素级结构和后续多模态扩展支持不足 |
| 统一走无结构纯文本抽取 | 不采用 | 会丢失 Markdown 标题结构，削弱当前分块策略 |

结论：文档处理层以 Docling 为主，优先保留源文档结构，并为表格、图片和后续多模态理解预留统一数据模型。

### 文档处理架构

当前版本将文档处理定义为独立子架构，而不是零散的文件解析逻辑。采用“统一流水线 + 按类型解析器 + 统一 Document 表示”的方式处理不同类型文档。

推荐流水线如下：

1. 文件发现
2. 类型识别
3. 解析器调度
4. 统一 `Document` 表示生成
5. 结构与元素标准化
6. 文本分块
7. 索引写入

该架构的核心目标是：

- 不让 `chunking` 直接依赖 Markdown/TXT/PDF 各自的实现细节。
- 让检索索引与资源读取都建立在统一文档表示之上。
- 为表格、图片、标题、文本块等元素保留共同的数据模型。

### 统一 Document 表示

不同解析器在进入 `chunking` 之前，都必须输出同一种标准 `Document` 表示。该表示至少应包含：

- 文档级 metadata
- 结构化章节/标题节点
- 文本元素
- 表格元素
- 图片元素
- 元素顺序与位置线索

当前版本对统一文档模型采用“固定核心字段 + 可扩展 metadata”的设计风格。

`Document` 顶层核心字段定义如下：

- `id`
- `source_path`
- `file_type`
- `title`
- `language`
- `elements`
- `metadata`

字段语义如下：

- `id`
  - 表示统一文档对象自身的稳定标识，可与 `doc_id` 保持一致。
- `source_path`
  - 表示相对于被索引目录的规范化相对路径。
- `file_type`
  - 表示文档源类型，例如 `md`、`txt`、`pdf`。
- `title`
  - 表示文档级标题；若无法抽取正式标题，可退化为文件名。
- `language`
  - 表示文档主语言，用于后续多语言检索与处理预留。
- `elements`
  - 表示该文档包含的统一元素列表。
- `metadata`
  - 表示非核心扩展字段容器。

当前版本的 `chunking` 只消费统一表示中的文本相关结构，但不得丢弃表格、图片或其它元素位点。这样做的原因是：

- 当前版本继续以文本检索为主。
- 后续多模态理解、表格检索、父块资源扩展都依赖这些元素仍然存在于文档模型中。

### Element 模型

统一文档中的 `Element` 也采用“固定核心字段 + 可扩展 metadata”的设计。

当前版本正式支持以下元素类型：

- `heading`
- `text`
- `table`
- `image`
- `list`
- `code_block`

其中，首版检索直接消费以下元素类型：

- `heading`
- `text`
- `list`
- `code_block`

以下元素类型在当前版本保留在文档模型中，但不直接进入首版检索链路：

- `table`
- `image`

`Element` 核心字段定义如下：

- `element_id`
- `type`
- `text`
- `order`
- `page`
- `metadata`

字段语义如下：

- `element_id`
  - 表示元素级稳定标识，用于 `Chunk.source_element_ids` 建立来源映射。
- `type`
  - 表示元素类型，取值必须来自当前版本支持的枚举集合。
- `text`
  - 表示元素的可文本化内容；对图片可为空，对表格可保留文本化摘要或留空。
- `order`
  - 表示元素在文档中的顺序位置。
- `page`
  - 表示元素所在页码；对无分页格式可为空。
- `metadata`
  - 表示元素级非核心扩展字段，例如位置、bbox、样式、父级结构线索等。

### Chunk 模型

为了让 `chunking`、`indexing`、`resources` 和 `retrieval` 之间的边界稳定，当前版本将 `Chunk` 定义为显式数据契约，而不是临时中间结果。

`Chunk` 采用“固定核心字段 + 可扩展 metadata”的设计，核心字段如下：

- `chunk_id`
- `doc_id`
- `text`
- `chunk_index`
- `source_element_ids`
- `heading_path`
- `section_title`
- `section_level`
- `metadata`

字段语义如下：

- `chunk_id`
  - 由 `doc_id + chunk_index` 派生，用于与 `rag://...#chunk-<n>` 保持一致。
- `doc_id`
  - 表示该 chunk 所属文档标识。
- `text`
  - 表示最终进入首版检索和资源读取的文本内容。
- `chunk_index`
  - 表示文档内最终可检索子块的顺序编号。
- `source_element_ids`
  - 表示构成该 chunk 的源元素 ID 列表，用于将 chunk 与原始文档元素建立显式关联。
- `heading_path`
  - 表示展示优先的标题链路文本。
- `section_title`
  - 表示该 chunk 当前所属章节标题。
- `section_level`
  - 表示当前章节层级；对无标题文档的退化节点固定为 `0`。
- `metadata`
  - 仅保留非核心扩展字段，不重复核心字段。

`Chunk` 是当前版本唯一的首版检索单元，也是 `rag://` 资源寻址最终落点。

### Document / Element / Chunk 关系规则

当前版本需要对三层模型之间的关系施加明确约束，避免不同模块对“什么是可检索单元”产生不同理解。

#### 1. Chunk 组装规则

`Chunk` 只能在同一结构上下文内由相邻可检索元素组装而成。这里的结构上下文由以下字段共同确定：

- `heading_path`
- `section_title`
- `section_level`

当前版本允许进入首版检索组装链路的元素类型为：

- `text`
- `list`
- `code_block`

`heading` 不单独形成最终检索 `Chunk`，而是作为结构上下文来源，用于补充：

- `heading_path`
- `section_title`
- `section_level`

`table` 与 `image` 当前版本不直接进入首版检索 `Chunk`。

组装规则如下：

- 按文档原始顺序遍历元素。
- 仅合并同一结构上下文内相邻的可检索元素。
- 达到 `chunk_size` 时切分。
- 使用 `chunk_overlap` 生成后续 chunk。
- 不允许跨章节、跨标题层级自由拼接 chunk。

#### 2. Chunk 与 Element 的映射规则

`Chunk` 与 `Element` 的关系采用显式映射，而不是隐式推断。

- 一个 `Chunk` 可以关联多个 `source_element_ids`。
- 一个 `Element` 也可以出现在多个 `Chunk` 中。
- 这种“一对多”仅允许由 overlap 或边界切分引起。
- 不允许跨结构上下文任意复制元素到不相关 chunk 中。
- `source_element_ids` 必须按原始文档顺序保存，便于后续资源回溯与上下文重建。

#### 3. 表格与图片的挂接规则

虽然 `table` 与 `image` 不直接进入首版检索链路，但它们不能在文档模型中成为无上下文的孤立元素。

当前版本采用以下挂接规则：

- `table` 与 `image` 优先挂接到同一 `heading_path`、`section_title`、`section_level` 下最近的前置文本 `Chunk`。
- 这里的“前置”按文档原始顺序定义，而不是按视觉距离单独判定。
- 若同一章节下不存在前置文本 `Chunk`，则退化挂接到该章节上下文。
- 若文档本身无可靠章节结构，则退化挂接到文档级上下文。
- 不允许跨章节、跨 `heading_path` 去挂接到其它文本 `Chunk`。
- 检索 chunk 不直接消费它们的内容。
- 相关关联信息应保存在 `Chunk.metadata` 中，例如：
  - `table_element_ids`
  - `image_element_ids`
- 上述关联字段必须按原始文档顺序保存。
- 当前版本仅在 `rag://...` 资源读取的 `<metadata>` 中对外暴露这些关联字段。
- `rag_search` 结果保持轻量，不返回 `table_element_ids` 或 `image_element_ids`。
- `rag://...` 资源读取只返回关联元素 ID 列表，不内联表格正文、图片说明或其它挂接内容。

这些关联字段的目的在于：

- 为 post-v1 表格问答预留入口
- 为 post-v1 图文理解与多模态检索预留入口
- 让资源读取和父级结构扩展时仍能找回相关非文本元素

#### 4. 当前版本的稳定约束

基于以上关系规则，当前版本必须满足以下稳定性要求：

- `heading` 是上下文源，不是首版独立检索单元。
- `Chunk.text` 只来自 `text`、`list`、`code_block`。
- `Chunk` 不得跨 `heading_path` 合并。
- `rag://corpus/<corpus-id>/<doc-id>#chunk-<n>` 继续只指向最终文本 `Chunk`。
- `table` / `image` 的存在可以补充关系信息，但不能改变首版资源寻址规则。
- 非文本元素存在与否，不应改变无关文本 `Chunk` 的 URI。

### 多模态预留边界

基于 Docling 的统一文档表示，当前版本将表格、图片、标题等元素纳入文档模型，但首版索引仍以文本检索为主。

当前版本明确采用以下边界：

- 表格、图片进入统一 `Document` 表示。
- 文本相关最终子块继续作为首版唯一检索单元。
- 表格、图片当前阶段不进入独立 embedding 检索链路。
- 表格、图片可在 metadata、父级映射或后续资源扩展中保留关联位点。

这样既不把 v1 做成多模态检索系统，也不会在架构上堵死后续的图文理解、表格问答或多模态 rerank。

#### 6. XML 构建

| 选项 | 结论 | 原因 |
|------|------|------|
| Python 标准 XML 库 | 采用 | 满足 RFC 中的 `<response>` 契约，避免字符串拼接错误 |
| 手工字符串拼接 | 不采用 | 转义、嵌套和结构一致性风险高 |
| 引入重型 XML 序列化框架 | 暂不采用 | 当前 XML 结构稳定且简单，没有必要增加依赖层级 |

结论：XML-first 契约继续使用标准 XML 库构建。

#### 7. 测试栈

| 选项 | 结论 | 原因 |
|------|------|------|
| `pytest` + TDD | 采用 | 最符合当前 Python 仓库和测试先行要求 |
| `unittest` 为主 | 不采用为主方案 | 可用，但在测试表达和参数化上不如 `pytest` 简洁 |
| 先实现后补测试 | 明确不采用 | 与 RFC 驱动和 TDD 要求冲突 |

结论：实现阶段按 TDD 推进，测试栈采用 `pytest`。

#### 总体选型原则

当前版本的总原则如下：

- MCP 协议层：采用开源官方 SDK。
- RAG 编排层：采用自定义实现。
- 存储与检索后端：复用成熟底层库。
- 返回契约与资源模型：严格以 RFC 为中心，不反向服从第三方框架默认抽象。

### 包结构与模块职责

当前版本采用按领域分层的 Python 包结构，以保持职责清晰并支持后续演进。推荐模块划分如下：

- `config`
  - 负责环境变量解析、默认参数加载、路径配置和运行模式配置。
- `ingestion`
  - 负责目录扫描、文件类型识别、Docling 驱动的解析器调度以及统一 `Document` 表示生成。
- `chunking`
  - 负责从统一 `Document` 表示中执行 TOC/标题优先分块、递归细分、`chunk_index` 生成和结构上下文提取。
- `indexing`
  - 负责全量重建流程、`corpus_id` / `doc_id` 生成，以及向量索引与关键词索引的同步构建。
- `retrieval`
  - 负责 `vector` / `keyword` 模式调度、结果聚合、mode 校验和统一结果格式化。
- `resources`
  - 负责 `rag://` URI 解析、资源读取和 metadata 回填。
- `transport`
  - 负责 FastMCP / 官方 Python SDK 接入、`stdio` / HTTP 启动入口以及 XML 响应序列化。

### 模块依赖方向

v1 强制采用单向依赖，避免实现阶段出现协议层与领域层相互缠绕。依赖规则如下：

- `transport` 可以依赖 `retrieval`、`resources`、`indexing`，但这些模块不得反向依赖 `transport`。
- `retrieval`、`resources`、`indexing` 可以依赖 `chunking`、`ingestion`、`config` 及底层存储实现。
- `chunking` 不得感知 MCP、XML、HTTP 或任何传输层概念。
- `resources` 不得自行实现检索调度逻辑，只能消费既有索引与 metadata 映射。
- `config` 作为底层公共模块，不依赖业务层模块。

该依赖方向的目标是：

- 后续引入 `hybrid` / `rerank` 时只改动 `retrieval` 层。
- 后续替换存储后端时不影响 `transport` 与 XML 契约。
- 保持分块、索引、资源读取逻辑可以单独测试。

### 默认参数

当前版本采用保守默认参数组，以优先保证结果稳定性、URI 可解释性和跨模式一致性：

- `chunk_size = 800`
- `chunk_overlap = 120`
- `top_k = 5`
- `keyword_top_k = 8`

参数语义如下：

- `chunk_size`
  - 用于控制章节递归细分后的目标子块大小。
- `chunk_overlap`
  - 用于控制相邻子块的最小重叠，减少切分边界丢失上下文。
- `top_k`
  - 用于 `vector` 模式的默认返回数量。
- `keyword_top_k`
  - 用于 `keyword` 模式的默认候选返回数量。

这些默认值可以被配置覆盖，但 RFC 将其视为 v1 的标准默认行为。

### 工具返回 XML 总契约

v1 中所有 MCP 工具成功结果、错误结果以及 `rag://` 资源读取结果都统一使用 XML，并以 `<response>` 作为根节点。

成功返回统一结构如下：

```xml
<response>
  <status>ok</status>
  <data>
    ...
  </data>
</response>
```

错误返回统一结构如下：

```xml
<response>
  <status>error</status>
  <error>
    <code>NO_ACTIVE_INDEX</code>
    <message>当前没有活动索引</message>
    <hint>请先调用 rag_rebuild_index</hint>
  </error>
</response>
```

约束如下：

- 根节点固定为 `<response>`。
- `status` 仅允许 `ok` 或 `error`。
- 所有公共字段均使用子元素表达，不使用 XML 属性。
- `<data>` 内部按工具使用固定子节点，不采用通用 `<item>` 承载全部返回。
- XML 必须使用标准 XML 库构建，避免字符串拼接导致的转义和结构错误。

### 工具级 XML 结构

不同工具在 `<data>` 中使用固定子节点：

- `rag_rebuild_index(directory_path)` 对应 `<index-rebuild-result>`
- `rag_index_status()` 对应 `<index-status>`
- `rag_search(query, mode, top_k=5)` 对应 `<search-results>`
- `rag://...` 资源读取对应 `<resource>`

其中推荐结构如下：

`rag_rebuild_index(directory_path)`：

```xml
<response>
  <status>ok</status>
  <data>
    <index-rebuild-result>
      <corpus_id>...</corpus_id>
      <source_directory>...</source_directory>
      <document_count>...</document_count>
      <chunk_count>...</chunk_count>
      <indexed_at>...</indexed_at>
    </index-rebuild-result>
  </data>
</response>
```

`rag_index_status()`：

```xml
<response>
  <status>ok</status>
  <data>
    <index-status>
      <has_active_index>true</has_active_index>
      <corpus_id>...</corpus_id>
      <source_directory>...</source_directory>
      <document_count>...</document_count>
      <chunk_count>...</chunk_count>
      <indexed_at>...</indexed_at>
    </index-status>
  </data>
</response>
```

`rag_search(query, mode, top_k=5)`：

```xml
<response>
  <status>ok</status>
  <data>
    <search-results>
      <query>...</query>
      <mode>vector</mode>
      <top_k>5</top_k>
      <result_count>...</result_count>
      <results>
        <result>
          <text>...</text>
          <title>...</title>
          <uri>rag://corpus/&lt;corpus-id&gt;/&lt;doc-id&gt;#chunk-0</uri>
          <score>...</score>
          <metadata>
            <corpus_id>...</corpus_id>
            <doc_id>...</doc_id>
            <chunk_index>0</chunk_index>
            <file_type>md</file_type>
            <title>...</title>
            <section_title>技术设计</section_title>
            <heading_path>RFC-0001 &gt; 技术设计 &gt; 检索模式与检索流水线</heading_path>
            <section_level>2</section_level>
            <relative_path>docs/example.md</relative_path>
            <chunk_length>512</chunk_length>
            <indexed_at>...</indexed_at>
          </metadata>
        </result>
      </results>
    </search-results>
  </data>
</response>
```

`rag://...` 资源读取：

```xml
<response>
  <status>ok</status>
  <data>
    <resource>
      <uri>rag://corpus/&lt;corpus-id&gt;/&lt;doc-id&gt;#chunk-0</uri>
      <text>...</text>
      <metadata>
        <corpus_id>...</corpus_id>
        <doc_id>...</doc_id>
        <chunk_index>0</chunk_index>
        <file_type>md</file_type>
        <title>...</title>
        <section_title>技术设计</section_title>
        <heading_path>RFC-0001 &gt; 技术设计 &gt; 检索模式与检索流水线</heading_path>
        <section_level>2</section_level>
        <relative_path>docs/example.md</relative_path>
        <chunk_length>512</chunk_length>
        <indexed_at>...</indexed_at>
        <table_element_ids>
          <id>tbl-12</id>
          <id>tbl-13</id>
        </table_element_ids>
        <image_element_ids>
          <id>img-2</id>
        </image_element_ids>
      </metadata>
    </resource>
  </data>
</response>
```

### 统一错误模型

所有工具与资源读取失败时统一返回 XML 错误对象：

```xml
<response>
  <status>error</status>
  <error>
    <code>...</code>
    <message>...</message>
    <hint>...</hint>
    <details>
      ...
    </details>
  </error>
</response>
```

v1 至少规范以下错误码：

- `NO_ACTIVE_INDEX`
- `INVALID_DIRECTORY`
- `EMPTY_DIRECTORY`
- `UNSUPPORTED_FILE_TYPE`
- `EMBEDDING_CONFIG_MISSING`
- `RESOURCE_NOT_FOUND`
- `INDEX_BUILD_FAILED`
- `SEARCH_FAILED`
- `UNSUPPORTED_SEARCH_MODE`
- `SEARCH_MODE_NOT_IMPLEMENTED`
- `VECTOR_INDEX_CONFIG_MISMATCH`

错误字段约束如下：

- `code`：稳定错误码，供测试和客户端分支处理使用。
- `message`：面向人类的直接错误描述。
- `hint`：面向调用方的下一步修复建议。
- `details`：可选扩展块，用于放置路径、字段名或底层异常摘要，但不得暴露敏感信息。

检索模式相关错误语义如下：

- `UNSUPPORTED_SEARCH_MODE`：调用方传入的 `mode` 不在架构定义的模式集合内。
- `SEARCH_MODE_NOT_IMPLEMENTED`：调用方传入的 `mode` 属于架构预留模式，但当前版本尚未实现，例如 `hybrid` 或 `rerank`。
- `VECTOR_INDEX_CONFIG_MISMATCH`：当前运行配置中的 `EMBEDDING_MODEL` 或 embedding 维度与活动索引 manifest 不一致；此时仅 `vector` 模式报错，`keyword` 检索与 `rag://...` 资源读取仍可用，调用方应重新执行 `rag_rebuild_index`。

### 回答流程边界

服务不负责 v1 主路径中的最终答案生成。推荐调用流程如下：

1. 上层 LLM 调用 `rag_search` 获取相关 chunk。
2. 上层 LLM 基于返回的 `text` 组织答案。
3. 上层 LLM 在回答中插入 `[](rag://...)` 形式的资源溯源链接。
4. 客户端如需校验引用，可进一步读取对应 `rag://` resource。

### HTTP 传输策略

HTTP 不作为 v1 默认启动能力。默认运行方式为本地 `stdio`，以适配本地 MCP 客户端与最小暴露面。只有在显式启用 HTTP 模式时，服务才监听网络端口并对外暴露同一套工具与资源能力。

该策略的目的包括：

- 降低本地开发阶段的默认攻击面。
- 避免在未配置鉴权前误将服务暴露到网络。
- 保持本地优先场景下的最小启动复杂度。

### Post-v1 演进方向

以下方向明确延期，但 v1 设计不应阻断这些演进：

1. 增量索引或单文件更新。
2. 多语料并存以及按语料查询。
3. 真正落地 `hybrid`、`rerank` 与更复杂的 query pipeline。
4. 更强的可观测性、评测体系与托管部署能力。
5. 面向远程 HTTP 模式的鉴权与访问控制。
6. 是否保留一个仅用于调试或回归测试的内置 answer tool。

---

## 安全性考虑

- 服务需要读取本地文件系统路径，因此必须对输入目录做合法性校验。
- HTTP 模式的暴露面高于本地 `stdio` 模式，应视为独立的运维场景。
- API 密钥必须通过环境变量提供，不能写入仓库追踪文件。
- `rag://` 应避免将本地绝对路径直接暴露为稳定公共契约；若内部需要保留路径，只能放在非稳定元数据中。
- 返回资源内容时需要控制元数据字段，避免无意泄露本地文件系统细节。
- HTTP 模式下的 `metadata` 默认保持与 `stdio` 一致，但仍不得包含本地绝对路径。

---

## 实施计划

1. 建立配置、导入、切分、索引、检索、资源与 MCP 接线的包结构。
2. 实现 Docling 主导的统一文档处理层，支持 Markdown、TXT 与 PDF 输入，并产出统一 `Document` 表示。
3. 在统一 `Document` 表示上实现“TOC/标题层级优先 + 递归细分”的分块流程，对无可靠标题结构的文档回退到通用递归分块。
4. 按领域分层建立 `config`、`ingestion`、`chunking`、`indexing`、`retrieval`、`resources`、`transport` 模块，并遵守单向依赖规则。
5. 实现全量重建索引流程，并同步构建 Chroma 向量索引与 BM25 / 倒排关键词索引。
6. 实现 `rag_search` 的 `vector` 与 `keyword` 模式，以及 `rag://` resource 读取能力。
7. 在 metadata 中补充 `section_title`、`heading_path`、`section_level` 等结构上下文字段。
8. 为表格、图片和其它非文本元素保留统一文档模型位点，但当前版本不纳入独立检索链路。
9. 为 parent-child 分块与检索预留数据模型扩展位，但当前版本不落地父块资源。
10. 为 `hybrid` 与 `rerank` 预留稳定 mode、错误语义和扩展接口，但当前版本不落地实现。
11. 以 RFC 中定义的保守默认参数实现分块与检索默认行为。
12. 补充索引、检索、资源读取与传输层测试。
13. 增加环境变量配置、URI 约定、HTTP 启动策略与上层 LLM 使用方式说明文档。

---

## 开放问题

- 未来若引入多语料并存，`corpus-id` 是否仍仅基于目录路径 hash，还是需要加入可见别名层？
- v1 之后若支持内容版本化，是否要在 `rag://` 中加入版本段而保持旧 URI 兼容？
- 是否需要为 `rag_search` 增加分页或游标机制，以适配更大结果集？
- `hybrid` 模式未来采用何种融合策略，例如 RRF、加权分数还是规则优先级？
- `rerank` 模式未来采用何种 reranker 实现，以及候选集默认大小如何设定？
- parent-child 模式落地时，是否需要引入父块级 `rag://` 资源，还是仅在 metadata 中提供父块引用？
- 默认参数未来是否需要针对不同文件类型使用不同的切分策略和参数组？
- 表格与图片在 post-v1 中应以独立资源、结构化文本，还是多模态向量的方式进入检索链路？

---

## 决策记录

- Status: `DRAFT`
- Decision date: pending
- Approvers: pending
- Notes:
  - v1 明确是本地优先方案。
  - 全量重建索引是产品决策，不是临时实现妥协。
  - retrieval-first 是当前阶段的主路径，最终答案由上层 LLM 负责。
  - 当前版本实际落地 `vector` 与 `keyword`，并正式为 `hybrid` 与 `rerank` 保留扩展位。
  - 当前版本默认采用“TOC/标题层级优先 + 递归细分”的分块策略，并为 parent-child 保留扩展位。
  - 当前版本的文档处理层以 Docling 为主，统一生成 `Document` 表示，并为多模态理解保留元素级位点。
  - 当前版本内部采用按领域分层的包结构，并以单向依赖约束模块关系。
  - 当前版本默认参数采用保守参数组：`chunk_size=800`、`chunk_overlap=120`、`top_k=5`、`keyword_top_k=8`。
  - 后续扩展应依靠清晰模块边界，而不是过早拆分服务。

---

## 参考资料

- MCP 规范与 SDK 文档
- OpenAI 兼容接口文档
- 当前仓库中的 RAG MCP 规划结论
