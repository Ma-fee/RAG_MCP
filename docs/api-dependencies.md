# API Dependencies Checklist

用于支撑 RFC-0001 开发，避免因为外部 API / SDK 边界不清而卡住实现。

## 1. 必需依赖

| 依赖 | 作用 | 关联模块 | 当前状态要求 |
|------|------|----------|--------------|
| MCP Python SDK / FastMCP | 暴露 tools、resources，支持 `stdio` / HTTP | `transport` | 必须接真实 SDK |
| SiliconFlow Embeddings API（OpenAI-compatible） | 为 chunk 和 query 生成 embedding | `config` `indexing` `retrieval` | 必须先定义 provider，再接真实 API |
| Chroma | 持久化向量和 metadata，执行向量检索 | `indexing` `retrieval` `resources` | 必须先定义 store，再接真实 Chroma |
| Docling | 解析 `.md` `.txt` `.pdf`，生成统一文档结构 | `ingestion` `chunking` | 必须先定义文档模型，再接真实解析器 |
| BM25 / 倒排索引库 | 实现 `keyword` 检索 | `indexing` `retrieval` | 必须先定义 keyword index，再选具体库 |

## 2. 先定义的抽象接口

### `EmbeddingProvider`

- `embed_documents(texts: list[str]) -> list[list[float]]`
- `embed_query(text: str) -> list[float]`
- `model_name() -> str`
- `embedding_dimension() -> int`

### `VectorStore`

- `upsert_chunks(...)`
- `search_by_vector(...)`
- `load(...)`
- `reset(...)`

### `KeywordIndex`

- `build(...)`
- `search(...)`
- `load(...)`

### 统一文档模型

- `Document`
- `Element`
- `Chunk`

要求：

- `chunking` 只能消费统一模型
- `chunking` 不能直接依赖 Docling
- `retrieval` 不能直接依赖解析器输出

## 3. 最低配置

Embedding API（当前选型：SiliconFlow）至少需要：

- `EMBEDDING_BASE_URL`（建议默认：`https://api.siliconflow.cn/v1`）
- `EMBEDDING_API_KEY`
- `EMBEDDING_MODEL`（当前建议：`Qwen/Qwen3-Embedding-0.6B`）

可选但建议：

- `EMBEDDING_TIMEOUT_SECONDS`（例如 `30`）
- `EMBEDDING_MAX_RETRIES`（例如 `2`）

连通性最小验证（不入库明文 token）：

```bash
curl -sS https://api.siliconflow.cn/v1/embeddings \
  -H "Authorization: Bearer $EMBEDDING_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model":"Qwen/Qwen3-Embedding-0.6B",
    "input":"hello embedding"
  }'
```

索引 manifest 至少记录：

- `corpus_id`
- `indexed_at`
- `embedding_model`
- `embedding_dimension`
- 当前活动索引目录

## 4. 哪些可以先用 mock 开发

可以先开发：

- `chunking`
- `resources` 的 URI 解析
- `resources` 的 XML 输出
- `retrieval` 的结果组装
- `retrieval` 的错误模型
- `indexing` 的 manifest 写入
- `indexing` 的活动索引切换
- `transport` 的 XML 序列化

前提：

- 提供 mock `EmbeddingProvider`
- 提供内存版 `VectorStore`
- 提供 fake `KeywordIndex`
- 使用手工构造的 `Document` fixture

## 5. 必须尽快接真实 API 的部分

不能长期停留在 mock 的能力：

- `transport` 的 MCP tool / resource 注册
- `ingestion` 的 Markdown / TXT / PDF 解析
- `indexing` 的真实 embedding 生成
- `retrieval.vector` 的真实向量查询
- Chroma 持久化目录加载与重启恢复

## 6. 模块依赖检查

| 模块 | 外部依赖 |
|------|----------|
| `config` | Embedding API 配置 |
| `ingestion` | Docling |
| `chunking` | 无直接外部依赖 |
| `indexing` | Embedding API、Chroma、BM25 库、Docling |
| `retrieval` | Embedding API、Chroma、BM25 库 |
| `resources` | Chroma 或本地 metadata 存储 |
| `transport` | MCP Python SDK / FastMCP |

## 7. 开发顺序

1. 定义 `Document`、`Element`、`Chunk`
2. 定义 `EmbeddingProvider`、`VectorStore`、`KeywordIndex`
3. 先用 mock / fake 打通 `chunking`、`resources`、`retrieval` 的基础流程
4. 接入 Docling，打通 `ingestion -> chunking`
5. 接入 Embedding API 和 Chroma，打通 `indexing -> retrieval.vector`
6. 接入 BM25 库，打通 `retrieval.keyword`
7. 接入 MCP SDK / FastMCP，暴露真实 tools / resources

## 8. 实现完成前必须确认

- 已选定 MCP SDK 或 FastMCP
- 已明确 Embedding API 请求入口和返回向量维度
- 已确认 Chroma 持久化目录方案
- 已确认 Docling 能稳定解析三类输入：`.md`、`.txt`、`.pdf`
- 已选定 BM25 库
- 已有 mock 版本用于单元测试
- 已有真实集成验证覆盖 embedding、vector search、document parsing、MCP 注册
