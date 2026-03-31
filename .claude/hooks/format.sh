#!/bin/bash
# ruff format — Python コードをフォーマット

set -e

PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$PROJECT_ROOT"

echo "[format] Running ruff format..."
ruff format .

echo "[format] Done."
