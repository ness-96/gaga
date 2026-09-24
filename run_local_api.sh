#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
PORT="${GAGA_API_PORT:-8765}"

exec "$PYTHON_BIN" -m uvicorn api:app --app-dir "$ROOT_DIR" --host 127.0.0.1 --port "$PORT"
