# Plan B：FastMCP 标准协议迁移

**日期**：2026-03-29
**依赖**：Plan A 完成后对接（ResourceStore 接口稳定后）
**方法**：TDD — 先写失败测试，再实现，再通过

---

## 背景

当前实现使用自定义 stdio JSON 协议和自写 ThreadingHTTPServer，不符合标准 MCP 协议规范。需要迁移到：
- **FastMCP**：标准 MCP 协议，工具注册、schema 自动生成、stdio/SSE transport
- **FastAPI**：作为 HTTP 层，提供资源访问端点（图片/表格直接 GET 返回）

---

## 文件变更清单

### 新增文件
| 文件 | 职责 |
|------|------|
| `src/rag_mcp/transport/mcp_server.py` | FastMCP server，注册四个 MCP tool |
| `src/rag_mcp/transport/fastapi_app.py` | FastAPI app，提供 image/table 资源 GET 端点 |
| `tests/unit/test_mcp_server.py` | MCP server 工具注册与调用单元测试 |
| `tests/unit/test_fastapi_app.py` | FastAPI 端点单元测试 |

### 修改文件
| 文件 | 改动 |
|------|------|
| `main.py` | 入口改为启动 FastMCP（stdio 或 SSE）+ FastAPI |
| `src/rag_mcp/config.py` | 新增 `mcp_transport: str`（stdio/sse）|
| `pyproject.toml` | 新增依赖：`fastmcp`, `fastapi`, `uvicorn` |
| `src/rag_mcp/transport/handlers.py` | 保留业务逻辑，解耦 XML 格式化（迁移期过渡）|

### 删除/废弃文件
| 文件 | 处理方式 |
|------|----------|
| `src/rag_mcp/transport/http_server.py` | 迁移完成后删除 |
| `src/rag_mcp/transport/stdio_server.py` | 迁移完成后删除 |
| `src/rag_mcp/xml_response.py` | MCP 工具响应改为 dict，不再需要 XML |

---

## Task B1：安装依赖，更新配置

**目标文件**：`pyproject.toml`、`src/rag_mcp/config.py`

### 步骤
1. 安装新依赖：
   ```bash
   uv add fastmcp fastapi uvicorn[standard]
   ```
2. 在 `AppConfig` 新增字段：
   ```python
   mcp_transport: str  # "stdio" 或 "sse"
   ```
   从环境变量读取：`os.getenv("MCP_TRANSPORT", "stdio")`
3. 更新 `.env.example`，补充 `MCP_TRANSPORT=stdio` 说明
4. 运行现有测试确认不破坏：`uv run pytest tests/`
5. commit: `feat(config): add mcp_transport config field, install fastmcp/fastapi`

---

## Task B2：实现 FastAPI 资源访问 App（TDD）

**目标文件**：`src/rag_mcp/transport/fastapi_app.py`
**测试文件**：`tests/unit/test_fastapi_app.py`

### 背景
FastAPI 负责两件事：
1. `GET /resource?uri=rag://...` — 返回 text/table 的 JSON，或 image 的二进制
2. `GET /assets/<doc_id>/<filename>` — 直接返回图片文件（供前端渲染）

### 步骤
1. **写失败测试**（使用 `httpx.AsyncClient` + FastAPI `TestClient`）：
   ```python
   def test_get_text_resource_returns_json(client, mock_resource_service):
       mock_resource_service.read.return_value = {
           "uri": "rag://corpus/c1/d1#text-0",
           "type": "text",
           "text": "测试文本",
           "metadata": {}
       }
       resp = client.get("/resource?uri=rag://corpus/c1/d1#text-0")
       assert resp.status_code == 200
       assert resp.json()["type"] == "text"

   def test_get_image_resource_returns_binary(client, mock_resource_service, tmp_path):
       img_file = tmp_path / "test.png"
       img_file.write_bytes(b"fake-png")
       mock_resource_service.read.return_value = {
           "uri": "rag://corpus/c1/d1#image-0",
           "type": "image",
           "image_path": str(img_file),
           "vlm_description": "测试图片",
           "metadata": {}
       }
       resp = client.get("/resource?uri=rag://corpus/c1/d1#image-0")
       assert resp.status_code == 200
       assert resp.headers["content-type"] == "image/png"

   def test_get_resource_not_found_returns_404(client, mock_resource_service):
       mock_resource_service.read.side_effect = ServiceException(...)
       resp = client.get("/resource?uri=rag://corpus/c1/d1#text-999")
       assert resp.status_code == 404
   ```
2. 运行测试，确认失败
3. **实现** `fastapi_app.py`：
   ```python
   from fastapi import FastAPI, HTTPException, Query
   from fastapi.responses import FileResponse, JSONResponse

   def create_app(resource_service: ResourceService, data_dir: Path) -> FastAPI:
       app = FastAPI(title="RAG MCP Resource API")

       @app.get("/resource")
       def get_resource(uri: str = Query(...)):
           resource = resource_service.read(uri)
           if resource["type"] == "image":
               return FileResponse(resource["image_path"], media_type="image/png")
           return JSONResponse(resource)

       @app.get("/health")
       def health():
           return {"status": "ok"}

       return app
   ```
4. 运行测试，确认通过
5. commit: `feat(transport): add FastAPI resource access app`

---

## Task B3：实现 FastMCP Server，注册四个工具（TDD）

**目标文件**：`src/rag_mcp/transport/mcp_server.py`
**测试文件**：`tests/unit/test_mcp_server.py`

### MCP 工具定义

四个工具（与现有 handler 对应）：

| MCP 工具名 | 参数 | 返回 |
|-----------|------|------|
| `rag_rebuild_index` | `directory_path: str` | `{status, corpus_id, doc_count, chunk_count}` |
| `rag_index_status` | 无 | `{status, corpus_id, doc_count, ...}` |
| `rag_search` | `query: str, mode: str, top_k: int=5` | `{results: [{uri, text, score, related: [uri]}]}` |
| `rag_read_resource` | `uri: str` | `{uri, type, text/vlm_description/markdown, related}` |

### 步骤
1. **写失败测试**：
   ```python
   def test_mcp_server_has_four_tools():
       server = create_mcp_server(handlers=mock_handlers, config=mock_config)
       tool_names = [t.name for t in server.list_tools()]
       assert "rag_rebuild_index" in tool_names
       assert "rag_index_status" in tool_names
       assert "rag_search" in tool_names
       assert "rag_read_resource" in tool_names

   def test_rag_search_returns_dict_with_results(mock_handlers):
       mock_handlers.retrieval.search.return_value = {
           "query": "test", "mode": "hybrid", "top_k": 5,
           "result_count": 1,
           "results": [{"uri": "rag://...", "text": "...", "score": 0.9, "related": []}]
       }
       server = create_mcp_server(handlers=mock_handlers, config=mock_config)
       result = server.call_tool("rag_search", {"query": "test", "mode": "hybrid"})
       assert result["result_count"] == 1

   def test_rag_rebuild_index_validates_directory(mock_handlers):
       mock_handlers.rag_rebuild_index.side_effect = ServiceException(...)
       result = server.call_tool("rag_rebuild_index", {"directory_path": "/nonexistent"})
       assert "error" in result
   ```
2. 运行测试，确认失败
3. **实现** `mcp_server.py`：
   ```python
   from fastmcp import FastMCP

   def create_mcp_server(handlers: ToolHandlers, config: AppConfig) -> FastMCP:
       mcp = FastMCP("RAG MCP Server")

       @mcp.tool
       def rag_rebuild_index(directory_path: str) -> dict:
           """重建指定目录的 RAG 索引。"""
           return handlers.rag_rebuild_index_dict(directory_path)

       @mcp.tool
       def rag_index_status() -> dict:
           """查询当前活动索引状态。"""
           return handlers.rag_index_status_dict()

       @mcp.tool
       def rag_search(query: str, mode: str = "hybrid", top_k: int = 5) -> dict:
           """在 RAG 索引中检索相关内容，返回文本块与关联资源 URI。"""
           return handlers.rag_search_dict(query=query, mode=mode, top_k=top_k)

       @mcp.tool
       def rag_read_resource(uri: str) -> dict:
           """读取指定 URI 的资源（文本/图片描述/表格）。"""
           return handlers.rag_read_resource_dict(uri)

       return mcp
   ```
   - 工具返回 dict，不再是 XML
   - `ToolHandlers` 新增 `*_dict()` 方法（返回 dict 而非 XML 字符串）
4. 运行测试，确认通过
5. commit: `feat(transport): add FastMCP server with four standard MCP tools`

---

## Task B4：扩展 ToolHandlers，新增 dict 返回方法

**目标文件**：`src/rag_mcp/transport/handlers.py`

### 步骤
1. **写失败测试**（`tests/unit/test_mcp_server.py` 补充）：
   ```python
   def test_rag_rebuild_index_dict_returns_dict(tmp_path):
       handlers = ToolHandlers(data_dir=tmp_path, embedding_provider=None)
       result = handlers.rag_rebuild_index_dict(str(tmp_path))
       assert isinstance(result, dict)
       assert "status" in result
   ```
2. 在 `ToolHandlers` 新增四个 `*_dict()` 方法：
   ```python
   def rag_rebuild_index_dict(self, directory_path: str) -> dict:
       """与 rag_rebuild_index 相同逻辑，返回 dict 而非 XML。"""
       ...

   def rag_index_status_dict(self) -> dict:
       ...

   def rag_search_dict(self, query: str, mode: str, top_k: int) -> dict:
       ...

   def rag_read_resource_dict(self, uri: str) -> dict:
       ...
   ```
   - 原有 XML 方法**保留不删**（迁移期兼容）
   - dict 结构与 XML 现有字段一一对应
3. 运行测试，确认通过
4. commit: `feat(transport): add dict-returning handler methods for FastMCP`

---

## Task B5：更新 main.py 入口

**目标文件**：`main.py`

### 步骤
1. **写失败测试**（`tests/unit/test_main.py` 补充）：
   ```python
   def test_main_stdio_uses_fastmcp(monkeypatch):
       monkeypatch.setenv("MCP_TRANSPORT", "stdio")
       # mock fastmcp run，验证被调用
       ...

   def test_main_sse_starts_uvicorn(monkeypatch):
       monkeypatch.setenv("MCP_TRANSPORT", "sse")
       monkeypatch.setenv("ENABLE_HTTP", "true")
       # mock uvicorn.run，验证被调用
       ...
   ```
2. 更新 `main.py`：
   ```python
   def main() -> None:
       cfg = AppConfig.from_env()
       embedding_provider = _build_embedding_provider(cfg)
       handlers = ToolHandlers(data_dir=cfg.data_dir, embedding_provider=embedding_provider)
       mcp = create_mcp_server(handlers=handlers, config=cfg)

       if cfg.mcp_transport == "sse" or cfg.enable_http:
           # FastAPI + FastMCP SSE 模式
           import uvicorn
           from rag_mcp.resources.service import ResourceService
           from rag_mcp.transport.fastapi_app import create_app
           fastapi_app = create_app(
               resource_service=ResourceService(cfg.data_dir),
               data_dir=cfg.data_dir
           )
           # 挂载 MCP SSE 端点到 FastAPI
           fastapi_app.mount("/mcp", mcp.sse_app())
           uvicorn.run(fastapi_app, host=cfg.http_host, port=cfg.http_port)
       else:
           # stdio 模式
           mcp.run(transport="stdio")
   ```
3. 运行测试，确认通过
4. 运行完整集成测试：`uv run python main.py` 启动 stdio，发送测试 MCP 请求
5. commit: `feat(main): migrate to FastMCP with FastAPI resource server`

---

## Task B6：删除旧实现，清理

### 步骤
1. 确认所有现有测试通过：`uv run pytest tests/`
2. 删除旧文件：
   - `src/rag_mcp/transport/http_server.py`
   - `src/rag_mcp/transport/stdio_server.py`
   - `src/rag_mcp/xml_response.py`
3. 删除 `ToolHandlers` 中原有 XML 方法（`handle_tool`、`*_xml()` 等）
4. 运行全量测试：`uv run pytest tests/`
5. commit: `refactor(transport): remove legacy http/stdio/xml transport`

---

## 验收标准

- `uv run pytest tests/` 全部通过
- `uv run python main.py` 以 stdio 模式启动，MCP 客户端可发现四个工具
- `MCP_TRANSPORT=sse uv run python main.py` 启动后：
  - `GET /health` 返回 `{"status": "ok"}`
  - `GET /resource?uri=rag://...#image-0` 返回图片二进制
  - `/mcp` 端点符合 MCP SSE 协议
- 无 XML 残留代码

---

## 执行顺序

```
B1（依赖安装）→ B2（FastAPI）→ B3（FastMCP）→ B4（Handlers）→ B5（main.py）→ B6（清理）
```