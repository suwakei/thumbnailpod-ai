# ThumbnailPot AI Backend

> YouTube クリエイター向けサムネイル自動生成を担う AI バックエンドサービス

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![Ruff](https://img.shields.io/badge/Linter-Ruff-D7FF64?logo=ruff&logoColor=black)](https://docs.astral.sh/ruff/)

---

## 目次

- [サービス概要](#サービス概要)
- [アーキテクチャ](#アーキテクチャ)
- [技術スタック](#技術スタック)
- [ディレクトリ構成](#ディレクトリ構成)
- [クイックスタート](#クイックスタート)
- [環境変数](#環境変数)
- [API エンドポイント](#api-エンドポイント)
- [テスト](#テスト)
- [Lint / フォーマット](#lint--フォーマット)
- [データベース](#データベース)
- [CI/CD](#cicd)
- [設計ドキュメント](#設計ドキュメント)

---

## サービス概要

ThumbnailPot AI Backend は、YouTube クリエイター向けサービス **ThumbnailPot** の AI 処理を担当するバックエンドサービスです。

```
ユーザー (フロントエンド)
        │
        ▼
  Go API サーバー  ──── VPC 内部通信 (X-Internal-Secret) ────▶  本サービス (FastAPI)
                                                                        │
                                                         ┌──────────────┼──────────────┐
                                                         ▼              ▼              ▼
                                                      OpenAI        AWS S3         AWS SQS
                                                    (DALL-E 3)   (画像保存)     (非同期ジョブ)
                                                         │                            │
                                                         ▼                            ▼
                                                     PostgreSQL                  Worker サービス
                                                    (ジョブ管理)               (SDXL / LoRA 学習)
```

**主な機能:**

| 機能 | 説明 |
|------|------|
| サムネイル生成 | DALL-E 3 / Stable Diffusion XL によるテキスト → 画像生成 |
| スタイル解析 | CLIP を用いたクリエイターのスタイルベクトル抽出 |
| スタイル学習 | LoRA による個人スタイルモデルのファインチューニング (SQS 非同期) |
| セグメンテーション | SAM (Segment Anything Model) による被写体マスク生成 |
| PSD 生成 | レイヤー付き Photoshop ファイルの自動組み立て |
| ジョブ管理 | 非同期ジョブのステータス追跡 |

---

## アーキテクチャ

本サービスは **4 層のクリーンアーキテクチャ** を採用しています。依存の向きは上から下のみです。

```
┌─────────────────────────────────────────────────────────┐
│                       API 層                             │
│   app/api/internal/   HTTP ハンドラー・認証・Pydantic 変換  │
└────────────────────────────┬────────────────────────────┘
                             │ 呼び出す
┌────────────────────────────▼────────────────────────────┐
│                     Service 層                           │
│   app/services/       AI 処理・外部 API 呼び出し            │
└────────────────────────────┬────────────────────────────┘
                             │ 呼び出す
┌────────────────────────────▼────────────────────────────┐
│                  Infrastructure 層                       │
│   app/infrastructure/  DB・S3・SQS の具体操作              │
└─────────────────────────────────────────────────────────┘
```

**設計上の主要な決定事項:**

- **モジュールレベルシングルトン** — 重いモデル (SDXL, SAM, CLIP) はリクエストをまたいで再利用
- **遅延ロード** — torch/diffusers 等の GPU ライブラリはコンテナ起動時ではなく初回リクエスト時にロード
- **スレッドプール委譲** — CPU/GPU バウンド処理は `asyncio.run_in_executor` 経由で実行
- **2 サービス構成** — FastAPI API サービス + SQS を監視する Worker サービス

---

## 技術スタック

### コア

| カテゴリ | ライブラリ | バージョン |
|----------|-----------|-----------|
| Web フレームワーク | FastAPI + Uvicorn | 0.115+ / 0.32+ |
| バリデーション | Pydantic v2 | 2.9+ |
| 非同期 HTTP | httpx | 0.27+ |
| 設定管理 | pydantic-settings | 2.5+ |

### データ・インフラ

| カテゴリ | ライブラリ | バージョン |
|----------|-----------|-----------|
| データベースドライバー | asyncpg | 0.30+ |
| マイグレーション | Alembic + SQLAlchemy Core | 1.13+ / 2.0+ |
| AWS (S3 / SQS) | aioboto3 | 13.0+ |

### AI / ML

| カテゴリ | ライブラリ | バージョン |
|----------|-----------|-----------|
| 画像生成 LLM | OpenAI (DALL-E 3) | 1.50+ |
| 画像生成モデル | diffusers (SDXL) | 0.31+ |
| ファインチューニング | peft + accelerate | 0.13+ / 1.1+ |
| ビジョンモデル | transformers (CLIP) | 4.46+ |
| ディープラーニング | PyTorch | 2.5+ |
| 画像処理 | Pillow + numpy | 11.0+ / 1.26+ |
| スタイル分類 | scikit-learn | 1.5+ |
| PSD | psd-tools | 1.9+ |

### 開発ツール

| カテゴリ | ツール |
|----------|--------|
| パッケージ管理 | uv |
| Lint / Format | Ruff |
| テスト | pytest + pytest-asyncio |
| コンテナ | Docker / Docker Compose |
| CI/CD | GitHub Actions → AWS ECS |

---

## ディレクトリ構成

```
thumbnailpod-ai/
├── app/
│   ├── main.py                        # FastAPI アプリ初期化・ルーター登録
│   ├── api/
│   │   └── internal/                  # HTTP ハンドラー (認証済みエンドポイント)
│   │       ├── generate.py            # POST /internal/generate
│   │       ├── style.py               # POST /internal/style/*
│   │       ├── segment.py             # POST /internal/segment
│   │       ├── psd.py                 # POST /internal/psd
│   │       └── jobs.py                # GET  /internal/jobs/{job_id}
│   ├── core/
│   │   ├── config.py                  # Pydantic Settings (環境変数)
│   │   ├── security.py                # X-Internal-Secret 検証
│   │   └── logging.py                 # ロギング設定
│   ├── schemas/                       # Pydantic リクエスト/レスポンスモデル
│   │   ├── generate.py
│   │   ├── style.py
│   │   ├── segment.py
│   │   ├── psd.py
│   │   └── job.py
│   ├── services/                      # ビジネスロジック・AI 処理
│   │   ├── generation/
│   │   │   ├── dalle.py               # DALL-E 3 サービス
│   │   │   └── stable_diffusion.py    # SDXL サービス
│   │   ├── style/
│   │   │   ├── analyzer.py            # CLIP スタイル解析
│   │   │   └── trainer.py             # SQS ジョブキューイング
│   │   ├── segment/
│   │   │   └── sam.py                 # SAM セグメンテーション
│   │   └── psd/
│   │       └── builder.py             # PSD ファイル生成
│   └── infrastructure/                # 外部システムクライアント
│       ├── database.py                # asyncpg プール・SQL 操作
│       ├── s3.py                      # S3 クライアント
│       └── sqs.py                     # SQS クライアント
├── migrations/
│   ├── env.py                         # Alembic 設定
│   └── versions/
│       └── 0001_initial_schema.py     # 初期スキーマ
├── tests/
│   ├── conftest.py                    # pytest フィクスチャ
│   └── api/
│       ├── test_generate.py
│       ├── test_style.py
│       ├── test_jobs.py
│       └── test_health.py
├── .github/
│   └── workflows/
│       └── ci.yml                     # Test → Build → Deploy
├── Dockerfile                         # API サービス用
├── Dockerfile.worker                  # Worker サービス用
├── docker-compose.yml                 # ローカル開発環境
├── alembic.ini
└── pyproject.toml
```

---

## クイックスタート

### 前提条件

以下がインストールされていることを確認してください。

- **Docker Desktop** 4.x+
- **Python 3.11+**
- **uv** (パッケージマネージャー)

```bash
# uv のインストール (未インストールの場合)
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

### 手順

#### 1. リポジトリのクローン

```bash
git clone <repository-url>
cd thumbnailpod-ai
```

#### 2. 環境変数の設定

```bash
cp .env.example .env
```

`.env` を開き、最低限以下の値を設定してください。

```dotenv
OPENAI_API_KEY=sk-...          # OpenAI API キー
INTERNAL_API_SECRET=any-secret # 任意の文字列 (ローカル開発時は何でも可)
DATABASE_URL=postgresql://thumbnailpod:thumbnailpod@localhost:5432/thumbnailpod
S3_BUCKET=thumbnailpod-local
SQS_QUEUE_URL=http://localhost:4566/000000000000/thumbnailpod-style-training
```

> **Note:** ローカル環境では S3 / SQS は LocalStack で代替します。実際の AWS 認証情報は不要です。

#### 3. Docker Compose でインフラを起動

```bash
docker-compose up -d postgres localstack
```

| サービス | URL | 用途 |
|----------|-----|------|
| PostgreSQL | `localhost:5432` | データベース |
| LocalStack | `localhost:4566` | S3 / SQS エミュレーター |

#### 4. 依存パッケージのインストール

```bash
uv pip install -e ".[dev]"
```

#### 5. DB マイグレーションの実行

```bash
alembic upgrade head
```

#### 6. 開発サーバーの起動

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

サーバーが起動したら以下で動作確認できます。

```bash
curl http://localhost:8000/health
# → {"status": "ok"}
```

インタラクティブな API ドキュメント (Swagger UI) は以下で確認できます。

```
http://localhost:8000/docs
```

#### 7. (オプション) Worker サービスの起動

SQS を監視するスタイル学習ジョブを実行する場合:

```bash
docker-compose up worker
```

---

### Docker Compose で全部まとめて起動する場合

```bash
docker-compose up
```

これで `api`・`worker`・`postgres`・`localstack` の全サービスが起動します。

---

## 環境変数

`app/core/config.py` で管理される全設定値の一覧です。

### 必須

| 変数名 | 説明 |
|--------|------|
| `OPENAI_API_KEY` | OpenAI API キー (DALL-E 3 利用) |
| `DATABASE_URL` | PostgreSQL 接続文字列 |
| `S3_BUCKET` | S3 バケット名 |
| `SQS_QUEUE_URL` | SQS キュー URL (スタイル学習ジョブ用) |
| `INTERNAL_API_SECRET` | Go API との共有シークレット (認証ヘッダー) |

### オプション (デフォルト値あり)

| 変数名 | デフォルト | 説明 |
|--------|-----------|------|
| `ENV` | `development` | 実行環境 (`development` / `production`) |
| `AWS_REGION` | `ap-northeast-1` | AWS リージョン |
| `SD_MODEL_ID` | `stabilityai/stable-diffusion-xl-base-1.0` | SDXL モデル ID |
| `CLIP_MODEL_ID` | `openai/clip-vit-large-patch14` | CLIP モデル ID |
| `SAM_MODEL_CHECKPOINT` | `sam_vit_h_4b8939.pth` | SAM チェックポイントパス |
| `IMAGE_WIDTH` | `1280` | 生成画像の幅 (px) |
| `IMAGE_HEIGHT` | `720` | 生成画像の高さ (px) |

---

## API エンドポイント

すべての `/internal/*` エンドポイントは `X-Internal-Secret` ヘッダーによる認証が必要です。

```
X-Internal-Secret: <INTERNAL_API_SECRET の値>
```

### エンドポイント一覧

| メソッド | パス | 認証 | 説明 |
|----------|------|------|------|
| `GET` | `/health` | 不要 | ヘルスチェック |
| `POST` | `/internal/generate` | 必要 | サムネイル生成 |
| `POST` | `/internal/style/analyze` | 必要 | スタイル解析 |
| `POST` | `/internal/style/train` | 必要 | スタイル学習ジョブのキューイング |
| `POST` | `/internal/segment` | 必要 | セグメンテーション |
| `POST` | `/internal/psd` | 必要 | PSD ファイル生成 |
| `GET` | `/internal/jobs/{job_id}` | 必要 | ジョブステータス取得 |

### リクエスト例

```bash
# サムネイル生成
curl -X POST http://localhost:8000/internal/generate \
  -H "Content-Type: application/json" \
  -H "X-Internal-Secret: your-secret" \
  -d '{
    "job_id": "550e8400-e29b-41d4-a716-446655440000",
    "prompt": "プロゲーマーが熱狂するシーン、ネオン色の背景",
    "engine": "dalle3"
  }'
```

詳細なリクエスト/レスポンス仕様は [API 設計書](.claude/docs/02-development-docs/03-api-design.md) を参照してください。

---

## テスト

### テストの実行

```bash
# 全テスト実行
pytest tests/ -v --tb=short

# 特定のファイルのみ
pytest tests/api/test_generate.py -v

# カバレッジ付き
pytest tests/ --cov=app --cov-report=term-missing
```

### テスト構成

外部サービス (OpenAI / S3 / SQS / DB) はすべてモックします。実際のサービスには接続しません。

```python
# モックパターン例
from unittest.mock import AsyncMock, patch

def test_generate_success(client, internal_headers):
    with patch("app.api.internal.generate._dalle") as mock:
        mock.generate = AsyncMock(return_value=GenerateResponse(...))
        response = client.post("/internal/generate", json={...}, headers=internal_headers)
    assert response.status_code == 200
```

### テストカテゴリ

各エンドポイントに対して以下を必ずカバーしています。

| カテゴリ | 内容 |
|----------|------|
| 正常系 | 期待通りのレスポンスが返ること |
| 認証エラー | ヘッダーなしで `403` が返ること |
| バリデーションエラー | 不正な入力値で `422` が返ること |

---

## Lint / フォーマット

コードスタイルは **Ruff** で統一しています。

```bash
# Lint チェック
ruff check .

# 自動修正
ruff check . --fix

# フォーマット
ruff format .
```

設定 (`pyproject.toml`):

```toml
[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "PLC"]
```

> **Note:** PR 作成前に `ruff check .` がクリーンな状態であることを確認してください。CI で自動チェックされます。

---

## データベース

### スキーマ概要

```
users
  └── style_models (1:many)       # LoRA スタイルモデル
  └── generation_jobs (1:many)    # 生成ジョブ
        └── generated_thumbnails (1:1)
              └── thumbnail_layers (1:many)  # PSD レイヤー情報
```

> **Note:** AI サービスが直接操作するのは `generation_jobs` テーブルのみです。それ以外は Go API が管理します。

### マイグレーション

```bash
# マイグレーションの適用
alembic upgrade head

# 新規マイグレーションファイルの作成
alembic revision --autogenerate -m "add_new_column"

# 現在のリビジョン確認
alembic current

# 1つ前に戻す
alembic downgrade -1
```

### 接続設定

asyncpg コネクションプールを使用しています。

- `min_size`: 2
- `max_size`: 10

---

## CI/CD

GitHub Actions による自動化パイプライン (`.github/workflows/ci.yml`):

```
push / PR
    │
    ▼
┌─────────────────────────────────────────┐
│  Test Job (全ブランチ)                    │
│  1. ruff check .                        │
│  2. alembic upgrade head                │
│  3. pytest tests/ -v --tb=short         │
└──────────────────┬──────────────────────┘
                   │ テスト通過後
                   ▼
┌─────────────────────────────────────────┐
│  Build Job                              │
│  1. Docker build (API サービス)          │
│  2. Docker build (Worker サービス)       │
└──────────────────┬──────────────────────┘
                   │ main ブランチのみ
                   ▼
┌─────────────────────────────────────────┐
│  Deploy Job                             │
│  1. ECR へ push (SHA タグ)              │
│  2. alembic upgrade head (本番 DB)      │
│  3. ECS サービスの強制更新               │
└─────────────────────────────────────────┘
```

**本番環境:**

| 項目 | 値 |
|------|-----|
| ECS クラスター | `thumbnailai-prod` |
| API サービス | `thumbnailai-ai-service` |
| Worker サービス | `thumbnailai-ai-worker` |
| ログ保持 | CloudWatch Logs (30 日間) |

---

## 設計ドキュメント

実装・バグ修正・レビューの前に該当する設計書を確認してください。

| ドキュメント | 参照すべき場面 |
|-------------|---------------|
| [アーキテクチャ設計](.claude/docs/02-development-docs/01-architecture-design.md) | 層をまたぐ実装・DI・非同期フロー |
| [データベース設計](.claude/docs/02-development-docs/02-database-design.md) | テーブル・SQL・マイグレーション |
| [API 設計](.claude/docs/02-development-docs/03-api-design.md) | ルーティング・レスポンス形式・ステータスコード |
| [エラーハンドリング](.claude/docs/02-development-docs/04-error-handling.md) | エラーのラップ・HTTP 変換 |
| [型定義](.claude/docs/02-development-docs/05-type-definition.md) | 型・enum・struct・interface の定義 |
| [テスト戦略](.claude/docs/02-development-docs/06-test-strategy.md) | テストの追加・修正 |
| [CI/CD 設計](.claude/docs/02-development-docs/07-cicd-design.md) | GitHub Actions・デプロイフロー |
| [セキュリティ設計](.claude/docs/02-development-docs/08-security-design.md) | 認証・認可・外部入力 |
| [パフォーマンス最適化](.claude/docs/02-development-docs/09-performance-optimization.md) | モデルロード・非同期処理 |
| [プロジェクト概要](.claude/docs/01-project-overview/01-thumbnailpod-backend-ai-concept.md) | サービス全体像の把握 |

---

## トラブルシューティング

### `alembic upgrade head` が失敗する

PostgreSQL が起動しているか確認してください。

```bash
docker-compose up -d postgres
# 起動を待ってから再実行
alembic upgrade head
```

### `INTERNAL_API_SECRET` による 403 エラー

`.env` の `INTERNAL_API_SECRET` とリクエストヘッダーの値が一致しているか確認してください。

```bash
curl -H "X-Internal-Secret: $(grep INTERNAL_API_SECRET .env | cut -d= -f2)" \
  http://localhost:8000/internal/jobs/test-id
```

### GPU が認識されない

GPU を使わない CPU モードでも動作します。SDXL・SAM は初回リクエスト時に自動的にロードされます。処理に時間がかかる場合があります。

---

<div align="center">

**ThumbnailPot AI Backend** — Built with FastAPI & PyTorch

</div>
