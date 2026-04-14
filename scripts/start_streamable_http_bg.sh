#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOG_DIR="${PROJECT_ROOT}/.rag_mcp_data/logs"
PID_FILE="${PROJECT_ROOT}/.rag_mcp_data/streamable_http.pid"
LOG_FILE="${LOG_DIR}/streamable_http.log"

mkdir -p "${LOG_DIR}"

if [[ -f "${PID_FILE}" ]]; then
  OLD_PID="$(cat "${PID_FILE}")"
  if [[ -n "${OLD_PID}" ]] && kill -0 "${OLD_PID}" 2>/dev/null; then
    echo "streamable-http server is already running (PID=${OLD_PID})"
    echo "log: ${LOG_FILE}"
    exit 0
  fi
  rm -f "${PID_FILE}"
fi

if [[ -x "${PROJECT_ROOT}/.venv/bin/python" ]]; then
  PYTHON_BIN="${PROJECT_ROOT}/.venv/bin/python"
else
  PYTHON_BIN="python3"
fi

(
  cd "${PROJECT_ROOT}"
  export PYTHONPATH="${PROJECT_ROOT}/src"
  export MCP_TRANSPORT="streamable-http"
  "${PYTHON_BIN}" -m main >>"${LOG_FILE}" 2>&1 &
  echo $! >"${PID_FILE}"
)

NEW_PID="$(cat "${PID_FILE}")"
echo "Started streamable-http server in background (PID=${NEW_PID})"
echo "log: ${LOG_FILE}"
echo "pid: ${PID_FILE}"
