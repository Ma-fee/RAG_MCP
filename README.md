# rag-mcp

基于 FastMCP 的 RAG 服务，通过标准 MCP 协议对外暴露文档检索能力。

已支持工具：
- `rag_rebuild_index` — 索引指定目录的文档
- `rag_index_status` — 查看当前索引状态
- `rag_search` — 关键词 / 向量搜索
- `rag_read_resource` — 读取资源内容（`rag://...` URI）

说明：`hybrid` / `rerank` 为预留模式，尚未实现。

---

## 安装

```bash
uv sync
```

---

## 配置

```bash
cp .env.example .env
# 编辑 .env，至少填入 EMBEDDING_API_KEY（vector 搜索必需）
```

核心环境变量：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `RAG_MCP_DATA_DIR` | `.rag_mcp_data` | 索引数据目录 |
| `MCP_TRANSPORT` | `stdio` | 传输模式：`stdio` 或 `sse` |
| `HTTP_HOST` | `127.0.0.1` | SSE 模式监听地址（`sse` 模式有效） |
| `HTTP_PORT` | `8787` | SSE 模式监听端口（`sse` 模式有效） |
| `EMBEDDING_API_KEY` | — | vector 搜索必填 |
| `EMBEDDING_BASE_URL` | `https://api.siliconflow.cn/v1` | Embedding 服务地址 |
| `EMBEDDING_MODEL` | `Qwen/Qwen3-Embedding-0.6B` | Embedding 模型 |
| `EMBEDDING_DIMENSION` | 自动检测 | 向量维度（可选） |
| `EMBEDDING_TIMEOUT_SECONDS` | `30` | 请求超时秒数 |
| `DEFAULT_TOP_K` | `5` | 默认返回结果数 |
| `KEYWORD_TOP_K` | `8` | 关键词检索候选数 |
| `CHUNK_SIZE` | `800` | 分块大小（字符数） |
| `CHUNK_OVERLAP` | `120` | 分块重叠（字符数） |

---

## 运行

### stdio 模式（默认，供 MCP 客户端接入）

```bash
uv run python main.py
```

### SSE 模式（HTTP 服务，供调试或 Web 客户端使用）

```bash
MCP_TRANSPORT=sse uv run python main.py
```

验证：
```bash
curl http://127.0.0.1:8787/health
# {"status": "ok"}
```

MCP 端点：`http://127.0.0.1:8787/mcp`

资源访问端点：`http://127.0.0.1:8787/resource?uri=rag://...`

---

## 接入 Claude Desktop

在 Claude Desktop 配置文件中添加：

```json
{
  "mcpServers": {
    "rag-mcp": {
      "command": "uv",
      "args": ["run", "python", "main.py"],
      "cwd": "/path/to/rag_mcp"
    }
  }
}
```

---

## 典型用法

1. 调用 `rag_rebuild_index`，传入文档目录路径（支持 `.md` / `.txt` / `.pdf`）
2. 调用 `rag_search`，指定查询词和模式（`keyword` 或 `vector`）
3. 通过 `rag_read_resource` 读取搜索结果中的资源 URI

---

## 测试

```bash
uv run pytest -q
```
