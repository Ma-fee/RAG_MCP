# rag-mcp

Phase 2 提供本地 `stdio` 运行模式，支持：

- `rag_rebuild_index`
- `rag_index_status`
- `rag_search`（`keyword` / `vector`）
- `rag_read_resource`（`rag://...`）

## Run

```bash
python -m rag_mcp.transport.stdio_server
```

## Environment

可选环境变量：

- `RAG_MCP_DATA_DIR`（默认 `.rag_mcp_data`）
- `EMBEDDING_API_KEY`（vector 检索必需）
- `EMBEDDING_BASE_URL`（默认 `https://api.siliconflow.cn/v1`）
- `EMBEDDING_MODEL`（默认 `Qwen/Qwen3-Embedding-0.6B`）
- `EMBEDDING_DIMENSION`（可选，和活动索引 manifest 一致时启用 vector）
- `EMBEDDING_TIMEOUT_SECONDS`（默认 `30`）
