# ThumbnailPot AI サービス — プロジェクト概要

## サービスの目的

YouTube クリエイター向け AI サムネイル生成サービス **ThumbnailPot** の AI バックエンドサービス。
Go バックエンド API（`thumbnailpot-back`）から VPC 内部で呼び出され、以下の AI 処理を担当する。

- **画像生成**: DALL-E 3 / Stable Diffusion XL による 1280×720 サムネイル生成
- **スタイル解析**: CLIP モデルによるカラーパレット抽出・構図分析・スタイル埋め込み生成
- **スタイル学習**: LoRA / ControlNet スタイル参照の訓練ジョブをキューイング
- **セグメンテーション**: SAM（Segment Anything Model）による被写体レイヤー分離
- **PSD 生成**: セグメンテーション結果から Photoshop 編集可能な PSD ファイルを組み立て

---

## 技術スタック

| 項目 | 内容 |
|---|---|
| 言語 | Python 3.11+ |
| Web フレームワーク | FastAPI + Uvicorn |
| バリデーション | Pydantic v2 |
| DB ドライバ | asyncpg（接続プール） |
| マイグレーション | Alembic（SQLAlchemy で定義） |
| HTTP クライアント | httpx（非同期） |
| AWS | aioboto3（S3・SQS） |
| 画像生成 | OpenAI DALL-E 3 / diffusers SDXL |
| スタイル解析 | transformers（CLIP）/ scikit-learn（k-means） |
| セグメンテーション | segment-anything（SAM） |
| PSD 生成 | psd-tools |
| テスト | pytest + pytest-asyncio |
| リンター / フォーマッター | ruff |

---

## サービス位置づけ

```
Internet
  │
  ▼
Go バックエンド API（thumbnailpot-back）  ← ユーザー向け公開 API
  │  VPC 内部通信（X-Internal-Secret ヘッダー）
  ▼
Python AI サービス（thumbnailpot-ai）  ← このリポジトリ（内部専用）
  │
  ├── OpenAI API（DALL-E 3）
  ├── AWS S3（画像・PSD ファイル保存）
  ├── AWS SQS（重い学習ジョブのキューイング）
  └── PostgreSQL（ジョブステータス更新のみ）
```

---

## API エンドポイント一覧

すべてのエンドポイントは `X-Internal-Secret` ヘッダーによる認証が必要。

| メソッド | パス | 説明 |
|---|---|---|
| GET | `/health` | ヘルスチェック（認証不要） |
| POST | `/internal/generate` | サムネイル画像生成（DALL-E 3 / SDXL） |
| POST | `/internal/style/analyze` | スタイル解析（CLIP）|
| POST | `/internal/style/train` | スタイル学習ジョブをキューイング |
| POST | `/internal/segment` | SAM セグメンテーション |
| POST | `/internal/psd` | PSD ファイル組み立て |
| GET | `/internal/jobs/{job_id}` | ジョブステータス確認 |

---

## データベースアクセス

このサービスが直接アクセスするテーブルは `generation_jobs` のみ。

| 操作 | 対象 |
|---|---|
| SELECT | ジョブステータスの取得（`GET /internal/jobs/{job_id}`） |
| UPDATE | ジョブステータス更新（`completed` / `failed`・`completed_at` セット） |

テーブル DDL は Alembic マイグレーション（`migrations/versions/`）で管理。

---

## 環境変数

| 変数名 | 説明 |
|---|---|
| `ENV` | 環境識別子（`development` / `production`） |
| `OPENAI_API_KEY` | OpenAI API キー（DALL-E 3 生成用） |
| `AWS_REGION` | AWS リージョン（デフォルト: `ap-northeast-1`） |
| `S3_BUCKET` | S3 バケット名（画像・PSD ファイル保存先） |
| `SQS_QUEUE_URL` | SQS キュー URL（スタイル学習ジョブ送信先） |
| `DATABASE_URL` | PostgreSQL 接続文字列 |
| `INTERNAL_API_SECRET` | Go API との共有シークレット（VPC 内部認証） |
| `SD_MODEL_ID` | SDXL モデル ID（デフォルト: `stabilityai/stable-diffusion-xl-base-1.0`） |
| `CLIP_MODEL_ID` | CLIP モデル ID（デフォルト: `openai/clip-vit-large-patch14`） |
| `SAM_MODEL_CHECKPOINT` | SAM チェックポイントファイルパス |

---

## ローカル開発

```bash
# docker-compose で API + PostgreSQL + LocalStack を起動
docker-compose up

# マイグレーション実行
alembic upgrade head

# 開発サーバー起動
uvicorn app.main:app --reload

# テスト実行
pytest tests/ -v
```

---

## フェーズ別実装状況

| フェーズ | 機能 | 状態 |
|---|---|---|
| Phase 1 | DALL-E 3 画像生成 | 実装済み |
| Phase 1 | CLIP スタイル解析 | 実装済み |
| Phase 1 | SQS スタイル学習キューイング | 実装済み |
| Phase 2 | SDXL 推論 | 実装済み（要 GPU） |
| Phase 2 | SAM セグメンテーション | 実装済み（要 GPU） |
| Phase 2 | PSD 生成（psd-tools） | 実装済み |
