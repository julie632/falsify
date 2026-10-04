#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if ! command -v uv >/dev/null 2>&1; then
  echo "Install uv from https://docs.astral.sh/uv/ before starting Falsify."
  exit 1
fi
uv sync --frozen
exec uv run uvicorn falsify.server:app --host 127.0.0.1 --port "${FALSIFY_PORT:-8765}"
