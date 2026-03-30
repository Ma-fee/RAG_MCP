---
rfc_id: RFC-0002
title: 索引质量改进：分块噪音、跨引用修复、表格关联与检索评分
status: DRAFT
author: admin
reviewers: []
created: 2026-03-30
last_updated: 2026-03-30
decision_date:
related_prds: []
related_rfcs:
  - RFC-0001
---

# RFC-0002: 索引质量改进：分块噪音、跨引用修复、表格关联与检索评分

## 概述

本 RFC 基于对真实生产索引构建结果（挖掘机维修手册 PDF，556 页）的实测分析，识别出当前 `rag-mcp` 索引管道中存在的四类质量缺陷，并为每类缺陷提出具体改进方案与评估依据。

问题涵盖：极短噪音分块（87/1299 chunks ≤20 字）、跨引用关联几乎完全失效（全库仅 2 条强关联）、表格资源与文本分块完全脱节（0/158 表格有 `related`）、关键词评分缺乏 IDF 权重。VLM 图像描述问题已知，列为低优先级，不在本 RFC 范围内。

预期结果：在不破坏现有接口的前提下，通过最小改动提升检索质量，使相关实测指标达到可接受基线。

---

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

RFC-0001 定义了 rag-mcp v1 架构，目前已完成 Plan A（A1–A8）全部实现，87 个测试通过，FastMCP 迁移也已完成（Plan B）。索引管道由以下模块组成：

```
docling 解析 → SourceDocument(elements) → ChunkAssembler → keyword_store + vector_store
                                        → ResourceStore  → resource_store + cross_reference
```

首次对真实 PDF 文档（556 页挖掘机维修手册）执行完整索引构建后，通过脚本逐层分析索引结果，发现了多个影响检索质量的系统性问题。

### 历史背景

- RFC-0001 在「开放问题」中预留了「表格与图片在 post-v1 中应以何种方式进入检索链路」的问题，本 RFC 部分回应该问题。
- `cross_reference.py` 的设计假设文本元素内嵌有 "Fig X-X" 等引用标签，但 docling 在解析时已将这些标签提取为图片的 `caption` 字段，导致文本元素内几乎没有可匹配的引用，该假设在实际数据中不成立。

### 术语表

| Term | Definition |
|------|------------|
| Chunk | ChunkAssembler 输出的检索单元，同时写入 keyword_store 和 vector_store |
| Element | docling 解析出的原子内容单元，类型为 text / image / table / heading |
| resource_store | 存储 text/image/table 级原始资源的 JSON，每条记录含 `related` / `related_weak` |
| keyword_store | 存储全部 chunks 的 JSON，用于基于词袋的关键词检索 |
| cross_reference | 负责在 resource_store 条目间建立强/弱关联的模块 |
| related | resource_store 条目间的强关联（明确引用，如 "见图 4-4"） |
| related_weak | resource_store 条目间的弱关联（同 heading_path 的位置邻近） |

---

## 问题陈述

### 问题一：极短噪音分块（87/1299 chunks ≤20 字符）

`ChunkAssembler._group_text_segments` 将同一 section 内所有文本元素合并，但不过滤极短的独立元素（如仅含标题文本的元素、页码残留）。当某 section 内只有一个极短元素时，这个元素会被单独输出为一个 chunk，如：

- `"Hydraulic Excavator"`（19 字符）
- `"Preface - -"`（11 字符）
- `"Weight"`（6 字符）

这类 chunk 占据 Chroma 向量槽位，在语义搜索中会与真实内容产生无意义的余弦相似度竞争，同时稀释关键词搜索的召回精度。

**实测数据**：1299 个 chunks 中，87 个（6.7%）文本长度 ≤20 字符。

### 问题二：cross_reference 跨引用几乎完全失效

`cross_reference.build_cross_references` 的策略是：扫描 text 元素的 `text` 字段，用正则匹配 "Fig X-X"、"图 X-X" 等引用标签，再与 image/table 的 `caption` 字段对照建立强关联。

**实际情况**：docling 在 PDF 解析时已将图注文本提取为独立 `caption` 字段，正文 text 元素内的引用标签几乎不存在。

**实测数据**：
- resource_store 4540 个 text 元素中，含 Fig/图 引用的仅 11 条（0.24%）
- 全库唯一引用标签 10 个，能匹配 caption 的仅 1 个
- 最终强关联 `related` 仅建出 2 条（应有数百条）
- 弱关联 `related_weak` 1461 条靠同 heading_path 位置邻近，非语义关联

问题根因：模块设计假设（引用在正文内嵌）与 docling 的实际输出（引用已提取为 caption）不一致。

### 问题三：表格资源与文本分块完全脱节

`_build_attachment_metadata`（`rebuild.py:168`）负责将 image/table 元素关联到其所在 section 的最后一个文本 chunk，以便在 keyword_store 条目中写入 `resource_metadata`（含 `image_element_ids`）。但该函数的实际实现只处理了 `image`，没有处理 `table`：

```python
# rebuild.py:199-202
if element.element_type == "table":
    bucket["table_element_ids"].append(element.element_id)  # 写入了 bucket
if element.element_type == "image":
    bucket["image_element_ids"].append(element.element_id)
```

`table_element_ids` 虽然写入了 `bucket`，但 resource_store 条目（`_table_entry`）的 `related` 字段从未被填充，chunk 的 `resource_metadata` 也从未通过 `table_element_ids` 建立反向关联。

**实测数据**：158 个 table 条目，`related` 全为空（0/158）。

### 问题四：关键词评分缺乏 IDF 权重

`keyword_index._overlap_score` 使用的是简单词袋交集比率：

```
score = |query_tokens ∩ doc_tokens| / |query_tokens|
```

这等价于查询词命中率（Recall），没有考虑词的区分度。结果：
- 含高频通用词（"oil"、"pressure"、"valve"）的短噪音 chunk 与含完整操作步骤的长 chunk 可能得到相同分数
- 没有惩罚在几乎所有文档中都出现的词

**实测数据**：chunk 平均长度 432.9 字符，最短 1 字符，最长 800 字符，评分未反映内容密度差异。

### 不处理的影响

- **Risk**: 用户对有图表支撑的技术问题（如「液压泵结构」「故障诊断步骤」）提问时，图表完全不可达，答案质量低于预期。
- **Cost**: 噪音 chunk 持续占据向量槽，劣化向量检索 top-k 精度。
- **Opportunity**: 当前 resource_store 中图表元素已完整存在，修复关联成本低，收益明显。

---

## 目标与非目标

### 目标（范围内）

1. 在 `ChunkAssembler` 中过滤极短分块（低于可配置阈值），减少噪音 chunk 数量。
2. 修复 `_build_attachment_metadata` 使 table 元素与所在 section 的 chunk 正确关联。
3. 在 `cross_reference` 中补充基于位置邻近的图表-文本强关联策略，替代失效的 caption 字符串匹配。
4. 将关键词评分从简单交集比率升级为 BM25，引入 IDF 权重。
5. 所有改动不破坏现有 MCP 工具接口、URI 格式和 resource_store schema。

### 非目标（范围外）

1. VLM 图像描述填充（已知问题，优先级低，后续单独处理）。
2. Chroma metadata 字段化重构（不影响检索正确性，可作独立优化）。
3. hybrid/rerank 检索模式实现（RFC-0001 开放问题，范围更大）。
4. 增量索引或文件监听。
5. parent-child chunk 分层策略。

### 成功标准

| 指标 | 当前值 | 目标值 |
|------|--------|--------|
| 极短 chunk 数（≤20字） | 87/1299（6.7%） | ≤10 |
| table 条目有 related | 0/158（0%） | ≥120/158（75%） |
| cross_reference 强关联数 | 2 | ≥200（覆盖有 caption 的图片） |
| 全部现有测试通过 | 87/87 | 87/87（不退化） |

---

## 评估标准

| 标准 | 权重 | 说明 |
|------|------|------|
| 检索质量提升幅度 | 高 | 强关联数、噪音 chunk 减少率 |
| 接口兼容性 | 高 | 不改变 MCP 工具签名、URI schema、resource_store 字段结构 |
| 实现复杂度 | 中 | 优先最小改动，避免引入新依赖 |
| 测试覆盖 | 中 | 改动需有对应单元测试，不退化现有 87 个测试 |
| 索引重建性能 | 低 | BM25 构建略慢可接受，不引入量级级别的退化 |

---

## 方案分析

### 问题一：极短噪音分块

#### 方案 A：在 ChunkAssembler 中加最小长度过滤

**描述**：在 `_group_text_segments` 的 `flush()` 中，若合并后文本长度低于 `min_chunk_length`（默认 30），则跳过该 segment 而非 yield。

**优点**：
- 改动位置单一（assembler.py 一处）
- 不影响 resource_store 的元素存储（resource_store 仍保留所有 element）
- 参数可配置，易于调整

**缺点**：
- 过滤掉的 segment 中若包含真实短标题（如设备型号代码），会丢失这部分检索入口
- 需要调整对应测试的预期 chunk 数量

**评估**：

| 标准 | 评级 | 备注 |
|------|------|------|
| 检索质量提升 | 高 | 直接减少 87 个噪音 chunk |
| 接口兼容性 | 高 | 只影响 chunk 数量，不改接口 |
| 实现复杂度 | 低 | ~5 行改动 |

**风险**：`min_chunk_length=30` 可能过滤掉少量有意义的短 chunk，建议配合实测调整阈值。

#### 方案 B：在 VectorIndex/KeywordIndex 写入时过滤

**描述**：在 `rebuild.py` 的 chunk 写入循环中，跳过长度低于阈值的 chunk。

**优点**：过滤逻辑与 chunker 解耦

**缺点**：`chunk_index` 会产生空洞（chunk-0、chunk-2 存在，chunk-1 被跳过），URI 中的序号不连续，增加调试难度；需在两个写入路径都加过滤。

**评估**：实现复杂度比方案 A 高，URI 空洞是额外隐患，不推荐。

---

### 问题二：cross_reference 跨引用修复

#### 方案 A：基于顺序位置的图表-文本强关联（替换 caption 匹配）

**描述**：在 `cross_reference.build_cross_references` 中，对没有通过 caption 匹配建立强关联的 image/table 条目，改用「同 doc_id 内，找该图表 element_id 在原始文档 elements 列表中位置，关联其前 N 个文本条目」的策略，写入 `related`（而非 `related_weak`）。

由于 resource_store 目前已有 `element_id` 字段，可以通过 element_id 排序重建文档内的顺序。

**优点**：
- 不依赖 caption 字符串匹配，对 docling 输出格式鲁棒
- 可覆盖 352 个有 caption 但 caption 未在正文出现的图片
- 保留 caption 字符串匹配作为第一优先级（精确匹配），位置关联作为 fallback

**缺点**：
- element_id 排序需要保证 resource_store 内 element_id 的字典序与文档内顺序一致（需验证 docling 输出）
- 引入「N 个前置文本条目」的超参，需确定合理默认值（建议 N=1，即直接前驱文本）

**评估**：

| 标准 | 评级 | 备注 |
|------|------|------|
| 检索质量提升 | 高 | 可从 2 条强关联提升至数百条 |
| 接口兼容性 | 高 | 只填充 related 字段，schema 不变 |
| 实现复杂度 | 中 | 需重构 cross_reference 的 fallback 逻辑 |

#### 方案 B：完全依赖 related_weak（维持现状）

**描述**：不修复强关联，依赖现有 1461 条 `related_weak`（同 heading_path 邻近）。

**优点**：无需改动

**缺点**：`related_weak` 粒度粗（同章节所有文本都被关联），语义信号弱；`related` 为空意味着图表无法被精确检索关联。

**评估**：不满足成功标准，不推荐。

---

### 问题三：表格 related 关联

#### 方案 A：在 rebuild._build_attachment_metadata 中同时反向填充 resource_store 的 table.related

**描述**：当前 `_build_attachment_metadata` 已将 `table_element_ids` 写入 chunk 的 `bucket`，但 resource_store 的 table 条目 `related` 从未被填充。在 `_build_and_persist_keyword_store` 中，构建 chunk→resource_metadata 的映射后，同时建立反向映射：table_element_id → chunk_uri，并回写到 resource_store 的对应 table 条目的 `related` 字段。

**优点**：
- 不改变 resource_store schema
- 复用已有的 `_build_attachment_metadata` 逻辑
- 改动集中在 rebuild.py

**缺点**：
- `resource_store._persist` 在 `_build_attachment_metadata` 执行前已被调用，需要调整调用顺序或增加一次覆写

**评估**：

| 标准 | 评级 | 备注 |
|------|------|------|
| 检索质量提升 | 中 | 表格可通过 related 被文本 chunk 检索关联 |
| 接口兼容性 | 高 | 只填充已有 related 字段 |
| 实现复杂度 | 低-中 | 需调整 rebuild.py 中的调用顺序 |

---

### 问题四：关键词评分 BM25

#### 方案 A：在 keyword_index 中实现 BM25

**描述**：在 `KeywordIndex` 构建时计算语料级 IDF，在 `search` 时使用 BM25 公式（k1=1.5, b=0.75）替代简单交集比率。BM25 公式：

```
BM25(q,d) = Σ IDF(t) * (tf(t,d) * (k1+1)) / (tf(t,d) + k1*(1-b+b*|d|/avgdl))
```

**优点**：
- 纯 Python 实现，无需新依赖
- 高频通用词（"oil"、"hydraulic"）自动降权
- 长 chunk 相比短 chunk 不再天然占优（length normalization）

**缺点**：
- `KeywordIndex` 构建时需要两遍扫描（先算 IDF，再构建索引），内存略增
- `persist_keyword_store` 需同时持久化 IDF 表或在加载时重算

**评估**：

| 标准 | 评级 | 备注 |
|------|------|------|
| 检索质量提升 | 中-高 | 区分度明显提升，尤其对技术手册高频词 |
| 接口兼容性 | 高 | `search()` 签名不变 |
| 实现复杂度 | 中 | ~50 行改动，需更新 keyword_store.json schema |

#### 方案 B：引入 rank_bm25 库

**描述**：使用 `rank_bm25` 第三方库替换现有评分逻辑。

**优点**：实现更可靠，有社区维护

**缺点**：引入新依赖，增加部署复杂度；`rank_bm25` 的内部数据结构不便于直接持久化为现有 `keyword_store.json` 格式。

**评估**：相比方案 A 收益不明显，增加依赖不值得，不推荐。

---

## 推荐方案

| 问题 | 推荐方案 | 理由 |
|------|----------|------|
| 极短噪音分块 | 方案 A：assembler 最小长度过滤 | 改动最小，位置准确 |
| cross_reference 失效 | 方案 A：位置邻近强关联 | 对 docling 输出鲁棒，caption 匹配保留为优先 |
| 表格 related 缺失 | 方案 A：rebuild.py 反向填充 | 复用已有逻辑，无 schema 变更 |
| 关键词评分 | 方案 A：原生 BM25 | 无新依赖，区分度提升明显 |

接受的权衡：
- 极短过滤阈值（30字符）可能漏过少量有意义的短代码/型号 chunk，可通过测试数据调整。
- BM25 需在 `keyword_store.json` 中增加 `idf` 字段，与旧索引文件不兼容，需重建索引。

---

## 技术设计

### 1. assembler.py — 最小长度过滤

```python
# ChunkAssembler.__init__ 新增参数
def __init__(self, chunk_size=800, chunk_overlap=120, min_chunk_length=30)

# _group_text_segments 的 flush() 中
def flush() -> _Segment | None:
    text = " ".join(current_text.split()).strip()
    if not text or len(text) < self.min_chunk_length:  # 新增
        return None
    ...
```

`min_chunk_length` 默认值 30，可通过 `rebuild_keyword_index` 传入。

### 2. cross_reference.py — 位置邻近强关联

当前 fallback 逻辑（`related_weak`，基于 heading_path 完全匹配）改为：

```
对每个无强关联的 image/table 条目：
  1. 按 element_id 在同 doc_id 内排序（el-N 的 N 升序）
  2. 找该条目在排序列表中的位置 pos
  3. 向前查找最近的 text 类型条目（pos-1, pos-2, ...，最多回溯 3 步）
  4. 若找到，写入 related（强关联），而非 related_weak
  5. 同时将该图表 URI 写入对应 text 条目的 related（双向）
  6. 原有 related_weak（同 heading_path 范围）保留，不删除
```

`element_id` 格式为 `el-{N}`，N 是整数，排序用 `int(element_id.split('-')[1])`。

### 3. rebuild.py — 表格 related 回写

```
当前执行顺序：
  resource_store.build(doc) → linked_entries = build_cross_references() → _persist(linked_entries)
  → chunker.chunk_document(doc) → _build_attachment_metadata()

修改后：
  resource_store.build(doc) → build_cross_references() → chunk_document() →
  _build_attachment_metadata() → 回写 table.related → 最后统一 _persist()
```

具体：将 `_build_attachment_metadata` 返回的 `table_element_ids` 映射为 chunk URI 后，在 `linked_entries` 中找到对应 table 条目，追加到其 `related` 字段，再调用 `_persist`。

### 4. keyword_index.py — BM25

`keyword_store.json` 新增顶层字段：

```json
{
  "corpus_id": "...",
  "avgdl": 432.9,
  "idf": {"oil": 0.23, "hydraulic": 0.41, ...},
  "entries": [...]
}
```

`KeywordIndex.search` 使用标准 BM25 公式，k1=1.5，b=0.75。旧索引文件无 `idf` 字段时退化为现有交集评分（向后兼容）。

---

## 安全性考虑

本 RFC 涉及的全部改动均在本地索引构建与查询路径内，不引入新的网络调用、用户输入解析路径或权限变更，无安全影响。

---

## 实施计划

### 阶段一：噪音过滤 + 表格关联（低风险，改动小）

1. `assembler.py`：添加 `min_chunk_length` 参数，`flush()` 中过滤。
2. `rebuild.py`：调整调用顺序，补 table.related 回写逻辑。
3. 更新相关单元测试（assembler、rebuild）。
4. 重建索引，验证：极短 chunk ≤10，table related ≥120。

### 阶段二：cross_reference 修复

1. `cross_reference.py`：实现 element_id 排序 + 向前回溯强关联逻辑。
2. 更新 `test_cross_reference` 测试。
3. 重建索引，验证强关联数 ≥200。

### 阶段三：BM25 评分

1. `keyword_index.py`：实现 BM25，持久化 `avgdl` 和 `idf`。
2. 向后兼容处理（无 `idf` 字段时降级）。
3. 更新 `test_keyword_index` 测试。
4. 重建索引，人工抽查评分结果合理性。

### 回滚策略

各阶段改动互相独立，可按阶段单独回滚。索引重建是全量操作，任何时候重建即可恢复到旧行为（通过 git revert 对应文件后重建）。

---

## 开放问题

1. **element_id 排序是否可靠？**
   - Context: `el-N` 中的 N 是否严格按文档顺序递增，需验证 docling 的实际输出。
   - Owner: 实现阶段验证
   - Status: Open

2. **min_chunk_length 最优阈值？**
   - Context: 30 字符是基于样本估算，可能需要针对不同文档类型调整。
   - Owner: 实现后用测试集验证
   - Status: Open

3. **BM25 idf 字段是否影响 manifest 兼容性检查？**
   - Context: `manifest.py` 当前只检查 `embedding_model` 和 `embedding_dimension`，BM25 idf 变化不会被检测到，旧索引继续使用旧评分不会报错。是否需要加版本字段？
   - Owner: 实现阶段决定
   - Status: Open

---

## 决策记录

> 待评审后填写。

**Status**: DRAFT

**Date**: pending

**Approvers**: pending

**Notes**:
- 本 RFC 不涉及 VLM 图像描述，VLM 作为独立后续任务处理。
- 四个改进点互相独立，可分阶段实施，不需要一次性全部上线。
- 优先阶段一（噪音过滤 + 表格关联），因为改动最小、收益确定。

---

## 参考资料

- [RFC-0001: RAG MCP v1 架构设计](RFC-0001-rag-mcp-v1-architecture.md)
- [BM25 算法原文: Robertson & Zaragoza (2009) "The Probabilistic Relevance Framework: BM25 and Beyond"](https://dl.acm.org/doi/10.1561/1500000019)
- Docling 元素模型文档（见 `docs/docling_json_format.md`）
- 索引质量分析脚本（本次分析会话产物，见 `.rag_mcp_data/indexes/` 目录）