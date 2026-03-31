#!/bin/bash
# ruff check — Python コードを静的解析・自動修正

set -e

PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$PROJECT_ROOT"

echo "[lint] Running ruff check --fix..."
ruff check . --fix

echo "[lint] Done."
