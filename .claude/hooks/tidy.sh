#!/bin/bash
# pip check — インストール済みパッケージの依存関係の整合性を確認する

set -e

PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$PROJECT_ROOT"

echo "[tidy] Running pip check..."
pip check

echo "[tidy] Done."
