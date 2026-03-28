# rag-mcp

Phase 4 提供本地 `stdio` 与显式启用的 `HTTP` 运行模式，支持：

- `rag_rebuild_index`
- `rag_index_status`
- `rag_search`（`keyword` / `vector`）
- `rag_read_resource`（`rag://...`）

## Run (Stdio)

```bash
python -m rag_mcp.transport.stdio_server
```

## Run (HTTP, opt-in)

```bash
ENABLE_HTTP=true HTTP_HOST=127.0.0.1 HTTP_PORT=8787 python main.py
```

HTTP 端点：`POST /tool`  
请求体：

```json
{"tool":"rag_index_status","args":{}}
```

## Environment

可选环境变量：

- `RAG_MCP_DATA_DIR`（默认 `.rag_mcp_data`）
- `ENABLE_HTTP`（默认 `false`）
- `HTTP_HOST`（默认 `127.0.0.1`）
- `HTTP_PORT`（默认 `8787`）
- `EMBEDDING_API_KEY`（vector 检索必需）
- `EMBEDDING_BASE_URL`（默认 `https://api.siliconflow.cn/v1`）
- `EMBEDDING_MODEL`（默认 `Qwen/Qwen3-Embedding-0.6B`）
- `EMBEDDING_DIMENSION`（可选，和活动索引 manifest 一致时启用 vector）
- `EMBEDDING_TIMEOUT_SECONDS`（默认 `30`）

## Smoke Check

```bash
bash scripts/e2e_phase4_smoke.sh
```
