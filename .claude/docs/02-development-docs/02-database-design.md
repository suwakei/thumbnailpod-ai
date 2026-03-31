# データベース設計規則

## 基本環境

- **DBMS**: PostgreSQL 15
- **ドライバ**: asyncpg（`asyncpg.Pool` による接続プール管理）
- **マイグレーション**: Alembic（`migrations/versions/` ディレクトリ）
- **スキーマ定義**: SQLAlchemy Core（ORM は使用しない）
- **ローカル環境**: docker-compose（postgres:15-alpine）

---

## AI サービスが使用するテーブル

このサービスは `generation_jobs` テーブルのみ直接操作する。
他のテーブル（`users`, `style_models`, `generated_thumbnails` 等）は Go バックエンドが管理する。

```
AI サービスのアクセス範囲
  └── generation_jobs
        ├── SELECT: status, error_message（ジョブ状態取得）
        └── UPDATE: status, error_message, completed_at（処理結果の書き込み）
```

---

## テーブル関係図（全体）

```
users（中心エンティティ）
  ├── style_models           1:多  ON DELETE CASCADE
  └── generation_jobs        1:多  ON DELETE CASCADE
       ├── generated_thumbnails  1:1  ON DELETE CASCADE
       │     └── thumbnail_layers  1:多  ON DELETE CASCADE
       └── ← AI サービスが status を更新
```

---

## テーブル設計サマリー

### users

```sql
CREATE TABLE users (
    id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    youtube_channel_id     VARCHAR(64)  NOT NULL UNIQUE,
    channel_name           VARCHAR(255) NOT NULL,
    plan                   plan_enum    NOT NULL DEFAULT 'free',
    generation_count_month INTEGER      NOT NULL DEFAULT 0,
    created_at             TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at             TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### style_models

```sql
CREATE TABLE style_models (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id            UUID               NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name               VARCHAR(255)       NOT NULL,
    type               style_model_type_enum NOT NULL DEFAULT 'style_ref',
    s3_key             VARCHAR(512),
    style_metadata     JSONB,
    source_video_count INTEGER            NOT NULL DEFAULT 0,
    status             style_model_status_enum NOT NULL DEFAULT 'pending',
    created_at         TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at         TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### generation_jobs

```sql
CREATE TABLE generation_jobs (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        UUID       NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    style_model_id UUID       REFERENCES style_models(id) ON DELETE SET NULL,
    prompt         TEXT       NOT NULL,
    status         job_status_enum NOT NULL DEFAULT 'pending',
    error_message  TEXT,
    created_at     TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at   TIMESTAMP WITH TIME ZONE
);
```

### generated_thumbnails

```sql
CREATE TABLE generated_thumbnails (
    id                  UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id              UUID         NOT NULL UNIQUE REFERENCES generation_jobs(id) ON DELETE CASCADE,
    s3_key              VARCHAR(512) NOT NULL,
    psd_s3_key          VARCHAR(512),
    width               INTEGER      NOT NULL DEFAULT 1280,
    height              INTEGER      NOT NULL DEFAULT 720,
    applied_to_video_id VARCHAR(64),
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### thumbnail_layers

```sql
CREATE TABLE thumbnail_layers (
    id           UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    thumbnail_id UUID         NOT NULL REFERENCES generated_thumbnails(id) ON DELETE CASCADE,
    label        VARCHAR(64)  NOT NULL,
    s3_key       VARCHAR(512) NOT NULL,
    sort_order   INTEGER      NOT NULL DEFAULT 0
);
```

---

## ENUM 型

```sql
CREATE TYPE plan_enum                AS ENUM ('free', 'creator', 'pro', 'business');
CREATE TYPE style_model_type_enum    AS ENUM ('style_ref', 'lora');
CREATE TYPE style_model_status_enum  AS ENUM ('pending', 'training', 'ready', 'failed');
CREATE TYPE job_status_enum          AS ENUM ('pending', 'processing', 'completed', 'failed');
```

Python 側の対応（`app/schemas/job.py`）：

```python
class JobStatus(StrEnum):
    PENDING    = "pending"
    PROCESSING = "processing"
    COMPLETED  = "completed"
    FAILED     = "failed"
```

---

## 接続プール（asyncpg）

`app/infrastructure/database.py` でモジュールレベルのシングルトンプールを管理する。

```python
_pool: asyncpg.Pool | None = None

async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(settings.database_url, min_size=2, max_size=10)
    return _pool
```

- `min_size=2`: 常時 2 接続を維持
- `max_size=10`: 最大 10 並列接続

---

## SQL パターン

### ジョブステータス更新（AI サービスの主要 DB 操作）

```python
async def update_job_status(
    job_id: UUID,
    status: JobStatus,
    error_message: str | None = None,
) -> None:
    pool = await get_pool()
    await pool.execute(
        """
        UPDATE generation_jobs
        SET status = $2, error_message = $3,
            completed_at = CASE WHEN $2 IN ('completed', 'failed') THEN NOW() ELSE NULL END
        WHERE id = $1
        """,
        job_id,
        status.value,
        error_message,
    )
```

### パラメータはプレースホルダを使う（SQL インジェクション対策）

```python
# 正
row = await pool.fetchrow(
    "SELECT status, error_message FROM generation_jobs WHERE id = $1",
    job_id,
)

# 誤（文字列結合は禁止）
q = f"SELECT status FROM generation_jobs WHERE id = '{job_id}'"
```

---

## マイグレーション規則

- ファイル名: `{4桁連番}_{内容}.py`（例: `0001_initial_schema.py`）
- **1ファイル = 論理的に関連するテーブルのセット**
- Alembic の `upgrade()` / `downgrade()` を必ず実装する
- ENUM 型は使用するテーブルと同じファイルで定義・削除する
- マージ済みのマイグレーションは編集しない（新ファイルで変更）

```python
def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
    op.create_table("users", ...)

def downgrade() -> None:
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS plan_enum")
```

---

## インデックス

| インデックス名 | テーブル | カラム | 理由 |
|---|---|---|---|
| `ix_style_models_user_id` | style_models | user_id | ユーザー別一覧取得 |
| `ix_generation_jobs_user_id` | generation_jobs | user_id | 履歴取得・上限チェック |
| `ix_generation_jobs_status` | generation_jobs | status | ジョブ状態フィルタ |
| `ix_generated_thumbnails_job_id` | generated_thumbnails | job_id | job_id からの JOIN |
| `ix_thumbnail_layers_thumbnail_id` | thumbnail_layers | thumbnail_id | レイヤー一覧取得 |
