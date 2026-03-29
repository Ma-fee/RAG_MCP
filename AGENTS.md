# Repository Guidelines

## Project Structure & Module Organization
Core code lives in `src/rag_mcp/`:
- `transport/`: stdio + HTTP entrypoints and shared handlers.
- `indexing/`, `retrieval/`, `resources/`: indexing, search, and `rag://` readback.
- `ingestion/`, `chunking/`, `embedding/`: document parsing, chunk assembly, and embedding client.

Tests are under `tests/`:
- `tests/unit/`: focused module tests.
- `tests/integration/`: cross-module behavior (phase parity/regression).
- `tests/e2e/`: end-to-end acceptance flow.

Plans and execution checklists are in `plan/`. Utility smoke script: `scripts/e2e_phase4_smoke.sh`.

## Build, Test, and Development Commands
- Install deps (example): `python -m pip install -e .[dev]`
- Run all tests: `pytest -q`
- Run key regression set:  
  `pytest -q tests/unit tests/integration/test_phase1_stdio_keyword_flow.py tests/integration/test_phase2_vector_keyword_parity.py tests/integration/test_phase3_structure_and_uri_stability.py`
- Run smoke checks: `bash scripts/e2e_phase4_smoke.sh`
- Start stdio server: `PYTHONPATH=src python -m rag_mcp.transport.stdio_server`
- Start HTTP server (opt-in):  
  `PYTHONPATH=src ENABLE_HTTP=true HTTP_HOST=127.0.0.1 HTTP_PORT=8787 python main.py`

## Coding Style & Naming Conventions
- Python 3.13+, 4-space indentation, type hints on public interfaces.
- Keep modules small and behavior-focused; prefer shared handler/service reuse over duplicated transport logic.
- Naming:
  - files/modules: `snake_case.py`
  - classes: `PascalCase`
  - functions/variables/tests: `snake_case`
- Preserve stable URI contract: `rag://corpus/<corpus-id>/<doc-id>#chunk-<n>`.

## Testing Guidelines
- Framework: `pytest`.
- Follow TDD: write failing test first, implement minimal fix, re-run target tests, then full regression.
- Test files: `test_<feature>.py`; test names should describe behavior explicitly.
- For HTTP tests requiring local bind, run outside restrictive sandboxes when needed.

## Commit & Pull Request Guidelines
- Use conventional prefixes seen in history: `feat:`, `fix:`, `refactor:`, `docs:`, `chore:`, `release:`, `merge:`.
- Keep commits atomic (one task/behavior per commit) and include related tests.
- PRs should include:
  - what changed and why,
  - affected phases/tasks,
  - verification evidence (`pytest -q` / smoke output),
  - config/env changes (`README`, `.env.example`, `pyproject.toml`) when applicable.

## Security & Configuration Tips
- Never commit real API keys; use `.env` and `.env.example`.
- HTTP transport is intentionally disabled by default (`ENABLE_HTTP=false`).
- Error responses must avoid leaking sensitive local paths or system details.
