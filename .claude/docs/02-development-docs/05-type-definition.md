# 型定義規則

## 基本方針

- スキーマ（リクエスト・レスポンス）は **Pydantic BaseModel** で定義する
- 文字列 Enum は **`StrEnum`** を使う（`Enum(str, Enum)` は使わない）
- `Any` 型は最小限に抑え、具体的な型で表現する
- オプショナルは `| None = None`（`Optional[X]` は使わない）

---

## StrEnum（文字列列挙型）

`StrEnum` で文字列ベースの列挙型を定義する。
Pydantic がリクエスト/レスポンスの自動バリデーション・シリアライズに使用する。

```python
from enum import StrEnum

# 正：StrEnum
class GenerationEngine(StrEnum):
    DALLE3 = "dalle3"
    SDXL   = "sdxl"

class JobStatus(StrEnum):
    PENDING    = "pending"
    PROCESSING = "processing"
    COMPLETED  = "completed"
    FAILED     = "failed"

# 誤：素の文字列定数
ENGINE_DALLE3 = "dalle3"  # 型安全でない
```

### 命名規則

| 対象 | 形式 | 例 |
|---|---|---|
| クラス名 | PascalCase | `GenerationEngine`, `JobStatus`, `TrainPhase` |
| メンバー名 | UPPER_SNAKE_CASE | `DALLE3`, `PENDING`, `STYLE_REF` |
| 値（文字列） | snake_case・小文字 | `"dalle3"`, `"pending"`, `"style_ref"` |

### 定義済み StrEnum

```python
# app/schemas/generate.py
class GenerationEngine(StrEnum):
    DALLE3 = "dalle3"
    SDXL   = "sdxl"

# app/schemas/job.py
class JobStatus(StrEnum):
    PENDING    = "pending"
    PROCESSING = "processing"
    COMPLETED  = "completed"
    FAILED     = "failed"

# app/schemas/style.py
class TrainPhase(StrEnum):
    STYLE_REF = "style_ref"  # Phase 1: ControlNet スタイル参照
    LORA      = "lora"       # Phase 2: LoRA ファインチューニング
```

---

## Pydantic BaseModel

### 定義場所

`app/schemas/` に機能単位でファイルを分けて定義する。

| ファイル | 内容 |
|---|---|
| `schemas/generate.py` | `GenerateRequest`, `GenerateResponse`, `GenerationEngine` |
| `schemas/job.py` | `JobStatus`, `JobStatusResponse` |
| `schemas/style.py` | `StyleMetadata`, `StyleAnalyzeRequest/Response`, `StyleTrainRequest/Response`, `TrainPhase` |
| `schemas/segment.py` | `SegmentRequest`, `SegmentResponse`, `Layer` |
| `schemas/psd.py` | `PSDBuildRequest`, `PSDBuildResponse`, `LayerInput` |

### フィールド定義ルール

```python
class GenerateRequest(BaseModel):
    # 必須フィールド（デフォルト値なし）
    job_id: UUID
    user_id: UUID
    prompt: str = Field(..., min_length=1, max_length=2000)

    # デフォルト値あり（オプショナル相当）
    engine: GenerationEngine = GenerationEngine.DALLE3
    width: int = 1280
    height: int = 720

    # 真のオプショナル（None 許容）
    style_model_id: UUID | None = None
    negative_prompt: str | None = None
```

### Field によるバリデーション

```python
# 文字列長
prompt: str = Field(..., min_length=1, max_length=2000)

# リスト件数
image_urls: list[HttpUrl] = Field(..., min_length=1, max_length=50)

# 説明（OpenAPI ドキュメント用）
color_palette: list[str] = Field(default_factory=list, description="Dominant hex colors")
```

### ネストした型

```python
class StyleMetadata(BaseModel):
    color_palette: list[str] = Field(default_factory=list)
    composition_features: dict = Field(default_factory=dict)
    clip_embedding: list[float] = Field(default_factory=list)

class StyleAnalyzeResponse(BaseModel):
    style_metadata: StyleMetadata  # ネストした Pydantic モデル
```

---

## ID フィールド

すべてのエンティティ ID は `uuid.UUID` 型を使う。

```python
from uuid import UUID

class GenerateRequest(BaseModel):
    job_id: UUID
    user_id: UUID
    style_model_id: UUID | None = None
```

- FastAPI が UUID 文字列を自動パース・バリデーションする
- 無効な UUID 文字列が来た場合、422 Unprocessable Entity が自動返却される

---

## URL フィールド

外部から受け取る URL は `HttpUrl` 型を使う。

```python
from pydantic import HttpUrl

class SegmentRequest(BaseModel):
    image_url: HttpUrl   # バリデーション済み URL

class StyleAnalyzeRequest(BaseModel):
    image_urls: list[HttpUrl]
```

Service 層で使用するときは `str()` に変換する：

```python
async with httpx.AsyncClient() as client:
    resp = await client.get(str(req.image_url), timeout=15)
```

---

## 設定型（pydantic-settings）

`app/core/config.py` で `BaseSettings` を使った設定クラスを定義する。

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    env: str = "development"
    openai_api_key: str = ""
    aws_region: str = "ap-northeast-1"
    s3_bucket: str = ""
    # ...

settings = Settings()
```

- 環境変数名は `UPPER_SNAKE_CASE`（例: `OPENAI_API_KEY` → `settings.openai_api_key`）
- `.env` ファイルを自動ロードする

---

## 型定義の配置まとめ

```
app/schemas/           ← リクエスト/レスポンス Pydantic モデル・StrEnum
app/core/config.py     ← pydantic-settings 設定クラス
app/core/security.py   ← 認証ロジック（依存性注入）
```
