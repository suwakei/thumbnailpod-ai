#!/bin/bash
# pip-audit — 依存ライブラリの既知脆弱性をスキャンする
# 事前インストール: pip install pip-audit

set -e

PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$PROJECT_ROOT"

if ! command -v pip-audit &> /dev/null; then
  echo "[vuln] pip-audit not found. Skipping. (install: pip install pip-audit)"
  exit 0
fi

echo "[vuln] Running pip-audit..."
pip-audit -r requirements.txt

echo "[vuln] Done."
