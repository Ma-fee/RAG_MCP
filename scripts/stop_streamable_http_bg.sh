#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PID_FILE="${PROJECT_ROOT}/.rag_mcp_data/streamable_http.pid"

if [[ ! -f "${PID_FILE}" ]]; then
  echo "No PID file found. Server may already be stopped."
  exit 0
fi

PID="$(cat "${PID_FILE}")"

if [[ -z "${PID}" ]]; then
  echo "PID file is empty. Cleaning up."
  rm -f "${PID_FILE}"
  exit 0
fi

if ! kill -0 "${PID}" 2>/dev/null; then
  echo "Process ${PID} is not running. Cleaning up stale PID file."
  rm -f "${PID_FILE}"
  exit 0
fi

echo "Stopping streamable-http server (PID=${PID})..."
kill "${PID}" 2>/dev/null || true

for _ in {1..20}; do
  if ! kill -0 "${PID}" 2>/dev/null; then
    rm -f "${PID_FILE}"
    echo "Stopped successfully."
    exit 0
  fi
  sleep 0.2
done

echo "Graceful stop timed out. Sending SIGKILL to PID=${PID}."
kill -9 "${PID}" 2>/dev/null || true
rm -f "${PID_FILE}"
echo "Force-stopped."
