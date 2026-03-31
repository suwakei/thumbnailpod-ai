# Python コーディング規則

## 基本方針

- Python 3.11+ の構文を使う（`X | None`、`match`、`StrEnum` 等）
- `Optional[X]` は使わず `X | None` を使う
- `Union[X, Y]` は使わず `X | Y` を使う
- 型アノテーションは必ず付ける

---

## インポート

### 順序（ruff が自動整理）

1. 標準ライブラリ
2. サードパーティ
3. ローカル（`app.*`）

```python
# 正
import logging
from uuid import UUID

import httpx
from fastapi import APIRouter

from app.core.config import settings
from app.schemas.generate import GenerateRequest
```

### 重いライブラリの遅延インポート

GPU 依存ライブラリ（torch・diffusers・transformers・segment_anything）はモジュールトップレベルでインポートしない。
使用する関数内で `import` する（コンテナ起動時のメモリ節約・起動時間短縮）。

```python
# 正：遅延インポート
def _load_pipeline(self):
    from diffusers import StableDiffusionXLPipeline  # noqa: PLC0415
    import torch  # noqa: PLC0415
    ...

# 誤：トップレベルインポート
import torch
from diffusers import StableDiffusionXLPipeline
```

`# noqa: PLC0415` コメントで ruff の「モジュールトップレベルでないインポート」警告を抑制する。

---

## 非同期

- I/O 操作は `async def` で定義する
- CPU/GPU バウンドな処理は `asyncio.run_in_executor(None, ...)` で実行する
- `requests` は使わず `httpx.AsyncClient` を使う
- `asyncio.sleep` で人工的な遅延を入れない

```python
# 正
async with httpx.AsyncClient() as client:
    resp = await client.get(url, timeout=15)

# 誤
import requests
resp = requests.get(url)  # 同期・イベントループブロック
```

---

## Pydantic モデル

- リクエスト/レスポンスクラス名は PascalCase + `Request` / `Response`
- フィールドは snake_case
- オプショナルは `| None = None`
- バリデーション制約は `Field(...)` で付与する

```python
# 正
class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000)
    style_model_id: UUID | None = None

# 誤
class GenerateRequest(BaseModel):
    prompt: Optional[str]  # Optional は使わない
    styleModelId: str       # camelCase は使わない
```

---

## StrEnum

文字列 Enum は `StrEnum` を使う（Python 3.11+）。

```python
from enum import StrEnum

class JobStatus(StrEnum):
    PENDING    = "pending"
    PROCESSING = "processing"
    COMPLETED  = "completed"
    FAILED     = "failed"
```

- メンバー名: UPPER_SNAKE_CASE
- 値（文字列）: snake_case・小文字

---

## ログ

```python
import logging
logger = logging.getLogger(__name__)  # モジュールごとに取得

logger.info("処理名 start field=%s", value)   # INFO: 開始・完了
logger.debug("詳細情報 field=%s", value)       # DEBUG: 詳細
logger.error("エラー内容 field=%s: %s", id, e) # ERROR: エラー
```

- `logger.info("msg %s" % value)` は使わず `logger.info("msg %s", value)` を使う（遅延評価）
- プロンプト全文・API キー・シークレットはログに含めない

---

## 例外処理

- 具体的な例外型でキャッチする（`except Exception as e` は最後の手段）
- サービス層からは `HTTPException` を raise する
- 内部エラーメッセージ（スタックトレース等）をレスポンスに含めない

```python
# 正
try:
    row = await pool.fetchrow(q, job_id)
except asyncpg.PostgresConnectionError as e:
    logger.error("DB connection error: %s", e)
    raise HTTPException(status_code=503, detail="Database unavailable")
```

---

## ruff 設定

`pyproject.toml` に従う。

```toml
[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "PLC"]
```

- `E`: pycodestyle エラー
- `F`: pyflakes
- `I`: isort（インポート順序）
- `PLC`: pylint convention（`PLC0415` = モジュール外インポート警告）
