# Spec: 索引质量改进（RFC-0002）

**日期**: 2026-03-30
**关联 RFC**: RFC-0002
**范围**: assembler 极短 chunk 过滤、BM25 关键词评分、table related 回写、cross_reference 位置邻近强关联

---

## 1. assembler — 极短 chunk 过滤

### 需求

`ChunkAssembler` 必须支持 `min_chunk_length` 参数，拒绝产出长度低于阈值的 chunk，消除噪音。

### 接口变更

```python
# src/rag_mcp/chunking/assembler.py
class ChunkAssembler:
    def __init__(
        self,
        chunk_size: int = 800,
        chunk_overlap: int = 120,
        min_chunk_length: int = 30,  # 新增
    ) -> None: ...
```

```python
# src/rag_mcp/chunking/chunker.py
class Chunker:
    def __init__(
        self,
        chunk_size: int = 800,
        chunk_overlap: int = 120,
        min_chunk_length: int = 30,  # 新增，透传给 ChunkAssembler
    ) -> None: ...
```

```python
# src/rag_mcp/indexing/rebuild.py
def rebuild_keyword_index(
    source_dir: Path,
    data_dir: Path,
    chunk_size: int = 800,
    chunk_overlap: int = 120,
    min_chunk_length: int = 30,  # 新增，透传给 Chunker
    embedding_provider: Any | None = None,
    vlm_client: Any | None = None,
) -> dict[str, Any]: ...
```

### 行为规范

| 场景 | 期望结果 |
|------|----------|
| segment 文本长度 < min_chunk_length | 该 segment 不产生任何 chunk |
| segment 文本长度 == min_chunk_length | 保留，产生 1 个 chunk |
| segment 文本长度 > min_chunk_length | 正常分块，行为与之前一致 |
| fallback_text（无 elements 时）长度 < min_chunk_length | 返回空列表 |
| min_chunk_length=0 | 与旧行为完全一致（无过滤） |
| min_chunk_length < 0 | 抛出 ValueError |

### 测试文件：`tests/unit/test_chunk_assembler.py`

需新增：
- `test_chunk_assembler_drops_short_segments` — 长度 < 30 的 segment 产生空列表
- `test_chunk_assembler_keeps_segments_at_min_length` — 长度恰好 == 30 的 segment 保留
- `test_chunk_assembler_min_chunk_length_zero_keeps_all` — min_chunk_length=0 时短文本也保留
- `test_chunk_assembler_negative_min_chunk_length_raises` — 负值抛 ValueError

---

## 2. keyword_index — BM25 评分

### 需求

`KeywordIndex.search()` 使用 BM25 评分替换当前简单 token 交集评分，对高频词自动降权，对长 chunk 做长度归一化。

### 算法参数（内部常量）

```
k1 = 1.5
b  = 0.75
```

### 接口变更

`search()` 签名不变，`KeywordIndex.__init__` 不变，`persist_keyword_store` 不变。
仅替换 `_overlap_score` 为 BM25 内部实现。

`keyword_store.json` schema 新增顶层字段：

```json
{
  "corpus_id": "...",
  "idf": { "<token>": <float>, ... },
  "avgdl": <float>,
  "entries": [ ... ]
}
```

`persist_keyword_store` 须同时写入 `idf` 和 `avgdl`。
`KeywordIndex` 加载时须读取 `idf` 和 `avgdl`；若不存在（旧格式），降级为原 overlap_score。

### 行为规范

| 场景 | 期望结果 |
|------|----------|
| 查询词在所有 chunk 中均出现（低 IDF） | 得分低于仅出现在少数 chunk 中的词 |
| 相同 token 命中，长 chunk vs 短 chunk | 长 chunk 得分低于短 chunk（length normalization） |
| 查询词不在任何 chunk 中 | score=0，不出现在结果中 |
| 旧格式 keyword_store（无 idf 字段） | 降级为 overlap_score，不抛异常 |

### 测试文件：`tests/unit/test_keyword_index.py`

需新增：
- `test_bm25_rare_term_scores_higher_than_common_term` — 稀有词得分 > 高频词
- `test_bm25_shorter_doc_scores_higher_than_longer_for_same_hit` — 相同命中，短文档得分更高
- `test_bm25_no_match_returns_empty` — 无匹配返回空列表
- `test_persist_keyword_store_writes_idf_and_avgdl` — 持久化后文件含 idf 和 avgdl 字段
- `test_keyword_index_loads_legacy_format_without_error` — 旧格式（无 idf）可正常加载和搜索

---

## 3. rebuild — table related 回写

### 需求

`_build_attachment_metadata` 目前只处理 image，需同时处理 table，使 resource_store 中 table 条目获得 `related` 指向包含该表格文本的 chunk URI。

### 行为规范

`_build_attachment_metadata` 返回的 `attachments` dict 结构不变：

```python
{
    chunk_index: {
        "image_element_ids": [...],
        "table_element_ids": [...],  # 已存在，但未被用于反向回写
    }
}
```

`_build_and_persist_keyword_store` 中，在构建 `entry` 的 `resource_metadata` 之后，须同时更新 `linked_entries` 中对应 table 条目的 `related` 字段，将 chunk 的 URI 加入。

具体：对每个 chunk entry，若 `attachment_meta_by_chunk` 中存在 `table_element_ids`，则：
- 找到 `linked_entries` 中 `element_id` 在该列表中且 `type == "table"` 的条目
- 将该 chunk 的 `uri` 追加到该 table 条目的 `related` 列表（若不存在则初始化）

### 测试文件：`tests/unit/test_rebuild_multimodal.py`

需新增：
- `test_rebuild_table_entries_have_related_links` — 索引构建后，resource_store 中 table 条目的 `related` 非空

---

## 4. cross_reference — 位置邻近强关联

### 需求

当前 cross_reference 的正则 caption 匹配策略在 docling 输出下几乎失效。需增加基于 element 顺序的位置邻近强关联策略，对没有正则匹配 related 的 image/table，自动链接前 N 个 text 条目。

### 接口变更

```python
# src/rag_mcp/indexing/cross_reference.py
def build_cross_references(
    entries: list[dict[str, Any]],
    proximity_window: int = 3,  # 新增
) -> list[dict[str, Any]]: ...
```

### 算法

```
对每个 doc_id 分组：
  按 entries 在列表中的原始顺序构建 ordered list
  遍历 ordered list：
    维护最近见到的 text entries 队列（maxlen=proximity_window）
    遇到 image 或 table：
      若已有 related（正则匹配），跳过
      否则：
        取队列中所有 text entries 加入 image/table 的 related（强关联）
        同时将 image/table 的 uri 加入这些 text entries 的 related
```

### 行为规范

| 场景 | 期望结果 |
|------|----------|
| image 前有 2 个 text，window=3 | image.related 包含这 2 个 text 的 uri |
| image 已有 related（正则匹配） | 跳过邻近逻辑，related 不变 |
| image 前无任何 text（文档首图） | related 为空，降级为 related_weak |
| proximity_window=0 | 邻近逻辑不执行，行为与之前一致 |
| 跨 doc_id | 不跨文档建立关联 |

### 测试文件：`tests/unit/test_cross_reference.py`

需新增：
- `test_proximity_links_image_to_preceding_text` — image 获得前 N 个 text 的强关联
- `test_proximity_skips_image_with_existing_related` — 已有 related 的 image 不被邻近逻辑覆盖
- `test_proximity_no_text_before_image` — 文档首图 related 为空
- `test_proximity_does_not_cross_doc_boundary` — 不跨 doc_id 建立关联
- `test_proximity_window_zero_skips_proximity` — window=0 时邻近逻辑不执行

---

## 实施顺序

1. 改动一（assembler）
2. 改动二（BM25）
3. 改动三（table related）
4. 改动四（cross_reference）

## 验收标准

- `pytest tests/unit/ -x -q` 全部通过（含新增测试）
- 现有测试无回归
