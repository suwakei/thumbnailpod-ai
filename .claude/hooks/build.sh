#!/bin/bash
# Python インポートチェック — 構文エラー・インポートエラーを即時検出する

set -e

PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$PROJECT_ROOT"

echo "[build] Checking Python imports..."
python -c "import app.main"

echo "[build] Done."
