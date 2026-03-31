#!/bin/bash
# pytest — ユニットテスト / API テストを実行する

set -e

PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$PROJECT_ROOT"

echo "[test] Running pytest..."
pytest tests/ -x --tb=short -q

echo "[test] Done."
