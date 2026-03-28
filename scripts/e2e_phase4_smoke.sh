#!/usr/bin/env bash
set -euo pipefail

pytest -q tests/integration/test_phase4_http_stdio_parity.py
pytest -q tests/e2e/test_v1_acceptance.py
