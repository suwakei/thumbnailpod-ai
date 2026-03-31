# CI/CD 設計

## GitHub Actions ワークフロー

`.github/workflows/ci.yml` で定義。`main` / `develop` ブランチへの push と PR をトリガーとする。

```
test → build → deploy（main のみ）
```

---

## test ジョブ

| ステップ | 内容 |
|---|---|
| PostgreSQL サービス起動 | postgres:15-alpine（:5432）|
| Python 3.11 セットアップ | `actions/setup-python@v5` |
| uv インストール | `pip install uv` |
| 依存関係インストール | `uv pip install --system -e ".[dev]"` |
| リント | `ruff check .` |
| マイグレーション実行 | `alembic upgrade head` |
| テスト実行 | `pytest tests/ -v --tb=short` |

---

## build ジョブ

`test` ジョブ成功後に実行。Docker イメージを 2 つビルドする。

| イメージ | Dockerfile | 用途 |
|---|---|---|
| `thumbnailai-api` | `Dockerfile` | AI Service（FastAPI）|
| `thumbnailai-worker` | `Dockerfile.worker` | AI Worker（重い学習処理） |

---

## deploy ジョブ（main ブランチのみ）

`build` ジョブ成功後、`github.ref == 'refs/heads/main'` の場合のみ実行。

| ステップ | 内容 |
|---|---|
| AWS 認証 | `aws-actions/configure-aws-credentials@v4` |
| ECR ログイン | `aws-actions/amazon-ecr-login@v2` |
| API イメージをビルド・プッシュ | `thumbnailai-ai-service:{sha}` → ECR |
| Worker イメージをビルド・プッシュ | `thumbnailai-ai-worker:{sha}` → ECR |
| DB マイグレーション実行 | `alembic upgrade head`（本番 DB） |
| AI Service をデプロイ | `aws ecs update-service --force-new-deployment` |
| AI Worker をデプロイ | `aws ecs update-service --force-new-deployment` |

---

## デプロイ戦略

- **イメージタグ**: GitHub commit SHA（`${{ github.sha }}`）でイメージを一意に識別
- **ECS デプロイ**: `--force-new-deployment` で新しいタスク定義を強制適用
- **クラスター名**: `thumbnailai-prod`
- **サービス名**: `thumbnailai-ai-service`（API）/ `thumbnailai-ai-worker`（Worker）

---

## 環境変数・シークレット

GitHub Actions シークレットとして管理する。

| シークレット | 用途 |
|---|---|
| `AWS_ACCESS_KEY_ID` | AWS 認証 |
| `AWS_SECRET_ACCESS_KEY` | AWS 認証 |
| `DATABASE_URL` | 本番 DB 接続文字列（マイグレーション用） |

---

## ローカルでの CI 再現

```bash
# ruff チェック
ruff check .

# マイグレーション実行
alembic upgrade head

# テスト実行
pytest tests/ -v --tb=short

# Docker ビルド確認
docker build -t thumbnailai-api:local -f Dockerfile .
docker build -t thumbnailai-worker:local -f Dockerfile.worker .
```

---

## フック連携

Claude Code の Stop フックで以下を自動実行する（`.claude/settings.json`）：

| フック | コマンド | タイミング |
|---|---|---|
| format | `ruff format .` | 回答生成後 |
| lint | `ruff check . --fix` | 回答生成後 |
| tidy | `pip check` | 回答生成後 |
| build | `python -c "import app.main"` | 回答生成後 |
