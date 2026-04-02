# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common commands

- Install dependencies:
  - `uv sync`
- Run server (default stdio transport):
  - `uv run python main.py`
- Run server in SSE transport:
  - `MCP_TRANSPORT=sse uv run python main.py`
- Run server in streamable HTTP transport:
  - `MCP_TRANSPORT=streamable-http uv run python main.py`
- Health check (SSE/HTTP transport):
  - `curl http://127.0.0.1:8787/health`

### Tests

- Run full test suite:
  - `uv run pytest -q`
- Run a single test file:
  - `uv run pytest -q tests/unit/test_main.py`
- Run a single test case:
  - `uv run pytest -q tests/unit/test_main.py::test_main_stdio_calls_mcp_run`
- Run integration smoke script:
  - `bash scripts/e2e_phase4_smoke.sh`

## High-level architecture

This project is a FastMCP-based RAG service exposing retrieval tools and `rag://` resources. The runtime is a single Python process with transport selection by `MCP_TRANSPORT`.

### 1) App bootstrap and dependency wiring

- `main.py` loads `.env`, reads `AppConfig`, wires optional providers (embedding, VLM, reranker), builds `ToolHandlers`, then starts FastMCP transport.
- `src/rag_mcp/config.py` is the central environment-to-config mapping.

### 2) Transport layer (protocol surface)

- `src/rag_mcp/transport/mcp_server.py` registers MCP tools/resources:
  - `rag_rebuild_index`, `rag_index_status`, `rag_search`, `rag_read_resource`, `rag_list_filenames`, `rag_list_sections`, `rag_section_retrieval`
- `src/rag_mcp/transport/handlers.py` is the orchestration boundary between transport and domain services (index rebuild, search, resource read).
- `src/rag_mcp/transport/fastapi_app.py` provides HTTP endpoints like `/health`, `/resource`, and `/assets/...` for non-MCP resource access.

### 3) Ingestion and chunking pipeline

- `src/rag_mcp/ingestion/docling_parser.py` parses `.pdf`/`.md`/`.txt` into a unified `Document`/`Element` model, with PDF-focused Docling + local cache/materialization behavior.
- `src/rag_mcp/chunking/toc_chunker.py` builds semantic chunks from PDF embedded TOC ranges.
- Current rebuild path is TOC-first and PDF-only (enforced in `src/rag_mcp/indexing/rebuild.py`), so PDFs without usable embedded TOC can fail indexing.

### 4) Index build and persistence

- `src/rag_mcp/indexing/rebuild.py` is the core indexing pipeline:
  1. Load source documents
  2. Build resource entries (`ResourceStore`)
  3. TOC-aware chunking
  4. Persist keyword store (BM25 stats + entries)
  5. Optionally persist vector index (Chroma) if embedding provider exists
  6. Atomically swap active manifest and clean old index dir
- `src/rag_mcp/indexing/keyword_index.py` handles keyword retrieval with BM25 scoring.
- `src/rag_mcp/indexing/vector_index.py` wraps Chroma persistence/query.
- `src/rag_mcp/indexing/manifest.py` controls active index pointer (`active_index.json`).

### 5) Retrieval and resources

- `src/rag_mcp/retrieval/service.py` uses keyword candidates + optional rerank (`src/rag_mcp/retrieval/reranker.py`), returning mode `rerank` in current unified path.
- `src/rag_mcp/resources/service.py` resolves `rag://` URIs against the active index:
  - text/chunk fragments from `keyword_store.json`
  - image/table fragments from `resource_store.json`
- URI parsing/contract is in `src/rag_mcp/resources/uri.py`.

## Data layout and runtime artifacts

Default data root: `.rag_mcp_data/`

- `active_index.json` — current active index manifest
- `indexes/idx-*/keyword_store.json` — chunk entries + BM25 stats
- `indexes/idx-*/resource_store.json` — image/table/text resources and relations
- `indexes/idx-*/chroma/` — vector persistence

Local parser/model caches used by ingestion:

- `.docling_models/`
- `.docling_cache/`
- `.element_cache/`

## Important constraints to preserve

- Keep URI compatibility: `rag://corpus/<corpus_id>/<doc_id>#<fragment>-<n>` (currently accepts `text|image|table|chunk`).
- `active_index.json` is the system source of truth for retrieval/read operations.
- Rebuild behavior is full rebuild + manifest swap; no incremental indexing path is currently implemented.