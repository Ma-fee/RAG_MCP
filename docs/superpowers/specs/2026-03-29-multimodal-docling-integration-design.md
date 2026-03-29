# 多模态 Docling 集成与分块策略改进设计

**日期**：2026-03-29
**状态**：已确认
**方案**：方案 B — Docling + GLM-4.6V 图表理解

---

## 背景与问题

当前 PDF 解析存在以下根本性问题：

1. `docling_parser.py` 实际使用 PyMuPDF，未使用 Docling
2. 整个 PDF 变成一个 Element，所有 chunk 的 `section_title` 均为文件名
3. 分块按字符数硬切，先抹平所有空白，破坏语义边界
4. 图片、表格内容无法被检索
5. `resource_service.py` 只能查 `keyword_store.json`，image/table 无法独立访问

---

## 整体架构

```
索引构建流水线：

PDF文件
  |
  v
DoclingParser（真正使用 Docling）
  ├── 版面分析（DocLayNet）
  ├── 表格识别（TableFormer）→ markdown + JSON
  ├── 图片区域裁剪 → 图片文件
  └── 文本提取 → 带 heading_path 的结构化文本
  |
  v
MultimodalProcessor
  ├── 图片 → GLM-4.6V API → 文字描述
  └── 表格 → 结构化存储
  |
  v
ResourceStore（三种模态独立存储）
  ├── TextResource   → rag://corpus/<cid>/<did>#text-<n>
  ├── ImageResource  → rag://corpus/<cid>/<did>#image-<n>
  └── TableResource  → rag://corpus/<cid>/<did>#table-<n>
  |
  v
CrossReferenceBuilder
  └── 建立 text <-> image <-> table 交叉关联
  |
  v
Chunker（结构感知）
  └── 按 heading_path 分块，图表引用替换为可点击 URI
  |
  v
VectorIndex + KeywordIndex
```

```
检索与返回：

Query
  |
  v
HybridSearch（向量 + BM25）
  |
  v
命中 text chunk
  |
  v
关联资源注入
"如图3-5所示" → [图3-5](rag://...#image-12)
  |
  v
返回结果（文本 + 资源 URI 列表）
```

---

## URI 格式

```
rag://corpus/<corpus-id>/<doc-id>#text-<n>    # 文本 chunk
rag://corpus/<corpus-id>/<doc-id>#image-<n>   # 图片资源
rag://corpus/<corpus-id>/<doc-id>#table-<n>   # 表格资源
```

**Breaking change**：原 `#chunk-<n>` 改为 `#text-<n>`，现有索引需 rebuild。

---

## 数据结构

### TextResource
```json
{
  "uri": "rag://corpus/abc123/doc456#text-42",
  "type": "text",
  "text": "调节阀工作压力范围为 20-35 MPa...",
  "heading_path": "Chapter 3 > 3.1 Hydraulic Pump > 3.1.2 Pressure Valve",
  "section_title": "3.1.2 Pressure Valve",
  "section_level": 3,
  "chunk_index": 42,
  "doc_id": "doc456",
  "page_numbers": [45, 46],
  "related": [
    "rag://corpus/abc123/doc456#image-12",
    "rag://corpus/abc123/doc456#table-8"
  ]
}
```

### ImageResource
```json
{
  "uri": "rag://corpus/abc123/doc456#image-12",
  "type": "image",
  "caption": "图3-5",
  "image_path": ".rag_mcp_data/assets/doc456/image-12.png",
  "vlm_description": "液压泵压力调节阀安装位置示意图...",
  "heading_path": "Chapter 3 > 3.1 Hydraulic Pump",
  "page_number": 45,
  "doc_id": "doc456",
  "related": [
    "rag://corpus/abc123/doc456#text-42"
  ]
}
```

### TableResource
```json
{
  "uri": "rag://corpus/abc123/doc456#table-8",
  "type": "table",
  "caption": "表3-2",
  "markdown": "| 参数 | 数值 | 单位 |\n|------|------|------|\n| 工作压力 | 20-35 | MPa |",
  "data_json": [{"参数": "工作压力", "数值": "20-35", "单位": "MPa"}],
  "heading_path": "Chapter 3 > 3.1 Hydraulic Pump > 3.1.2 Pressure Valve",
  "page_number": 46,
  "doc_id": "doc456",
  "related": [
    "rag://corpus/abc123/doc456#text-42"
  ]
}
```

### 磁盘存储布局
```
.rag_mcp_data/indexes/<index-id>/
├── keyword_store.json        # 现有，text chunk BM25
├── resource_store.json       # 新增，三种 resource 元数据
├── chroma/                   # 现有，向量索引
└── assets/
    └── <doc-id>/
        ├── image-12.png
        └── image-13.png
```

---

## 交叉关联建立策略

### 关联来源（优先级从高到低）

| 类型 | 方式 | 置信度 | 字段 |
|------|------|--------|------|
| 正则标注匹配 | 扫描"如图3-5""见表3-2" | 高 | `related` |
| Docling 同页空间相邻 | 同页 bounding box 邻近 | 中 | `related` |
| 同 heading_path 兜底 | 同章节内所有资源 | 低 | `related_weak` |

### 正则模式
```python
# 中文
r"如图\s*(\d+[-–]\d+)"        # 如图3-5
r"见图\s*(\d+[-–]\d+)"        # 见图3-5
r"图\s*(\d+[-–]\d+)\s*所示"   # 图3-5所示
r"表\s*(\d+[-–]\d+)"          # 表3-2

# 英文
r"[Ff]igure\s*(\d+[-\.]\d+)"  # Figure 3-5
r"[Tt]able\s*(\d+[-\.]\d+)"   # Table 3-2
```

### 建立时序
```
1. 提取所有 ImageResource，建立 caption→uri 映射表
2. 遍历 TextResource，正则扫描，写入双向 related[]
3. Docling 同页空间关联兜底
4. 文本内图表引用替换为 markdown 链接
```

---

## 改动范围

### 修改文件

| 文件 | 改动内容 |
|------|----------|
| `ingestion/docling_parser.py` | 真正使用 Docling 解析 PDF，提取结构化 Element |
| `indexing/rebuild.py` | 插入 ResourceStore.build 和 CrossReference.build |
| `resources/service.py` | 扩展支持 #image- 和 #table- URI 读取 |

### 新增文件

| 文件 | 职责 |
|------|------|
| `ingestion/vlm_client.py` | GLM-4.6V API 调用封装 |
| `indexing/resource_store.py` | resource_store.json 读写 |
| `indexing/cross_reference.py` | 交叉关联建立逻辑 |

---

## VLM 配置

```
MULTIMODAL_BASE_URL=https://api.siliconflow.cn/v1
MULTIMODAL_MODEL=zai-org/GLM-4.6V
```

API Key 通过 `MULTIMODAL_API_KEY` 环境变量注入。

VLM 调用为同步阻塞，建索引时每张图片顺序等待 API 返回。

---

## 数据流时序

```
rag_rebuild_index
  |
  ├─ 1. DoclingParser.parse(pdf) → Document（含 image/table/text Elements）
  |
  ├─ 2. ResourceStore.build(document)
  |       ├─ image elements → 裁剪图片 → GLM-4.6V → vlm_description
  |       ├─ table elements → markdown + data_json
  |       └─ 全部写入 resource_store.json + 复制图片到 assets/
  |
  ├─ 3. CrossReference.build(resource_store)
  |       └─ 建立 related 关联，更新 resource_store.json
  |
  ├─ 4. Chunker.chunk(document) → text chunks
  |       └─ 图表引用替换为可点击 URI
  |
  └─ 5. persist keyword_store + vector_index（URI 格式改为 #text-<n>）
```

---

## 返回效果示例

```markdown
调节阀工作压力范围为 20-35 MPa，调整时需先松开锁紧螺母，
如 [图3-5](rag://corpus/abc123/doc456#image-12) 所示，
具体参数见 [表3-2](rag://corpus/abc123/doc456#table-8)。

---
来源：Chapter 3 > 3.1 Hydraulic Pump > 3.1.2 Pressure Valve（第45页）
```

---

## 开放问题

- GLM-4.6V 调用并发/缓存策略（当前为同步阻塞，后续可优化）
- 跨页表格的合并策略（Docling TableFormer 支持，需验证）
- `related_weak` 是否需要在检索结果中展示
- image/table resource 是否也需要加入 BM25 keyword 索引（当前只进向量索引）
