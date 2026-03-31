# エラーハンドリング規則

## 基本方針

- **内部エラーの詳細をクライアントに返さない**（スタックトレース・SQL・ファイルパス等）
- Pydantic バリデーションエラー（422）はフレームワークが自動処理するため、ハンドラーで対処不要
- 予期したドメインエラー（リソース不存在等）は `HTTPException` で明示的に返す
- 予期しない例外はミドルウェアが 500 に変換する（FastAPI デフォルト）

---

## エラーの伝播フロー

```
Infrastructure 層（DB・S3・SQS・外部 API）
  例外をそのまま上位に伝播（または ValueError / RuntimeError でラップ）
      ↓
Service 層（AI 処理・ビジネスロジック）
  HTTPException を raise するか、例外をそのまま上位に伝播
      ↓
Handler 層（FastAPI ルーター）
  HTTPException → FastAPI が JSON レスポンスに変換
  その他の例外 → 500 Internal Server Error（詳細は返さない）
```

---

## HTTPException の使い方

### 404 Not Found（リソースが存在しない）

```python
# app/infrastructure/database.py
row = await pool.fetchrow("SELECT ... FROM generation_jobs WHERE id = $1", job_id)
if row is None:
    raise HTTPException(status_code=404, detail="Job not found")
```

### 403 Forbidden（認証失敗）

```python
# app/core/security.py
async def verify_internal_secret(api_key: str = Security(_api_key_header)) -> None:
    if api_key != settings.internal_api_secret:
        raise HTTPException(status_code=403, detail="Forbidden")
```

### 外部 API エラーのラップ

外部 API（OpenAI）のエラーはキャッチして 500 として返す。
エラーの詳細はログには出すが、レスポンスには含めない。

```python
try:
    response = await self._client.images.generate(...)
except Exception as e:
    logger.error("DALL-E generation failed job_id=%s: %s", req.job_id, e)
    raise HTTPException(status_code=500, detail="Image generation failed")
```

---

## Pydantic バリデーションエラー（422）

FastAPI が自動的に処理するため、ハンドラーで `try/except` を書かない。

```python
class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000)
    engine: GenerationEngine = GenerationEngine.DALLE3

# prompt="" → 422 自動返却（min_length 違反）
# engine="unknown" → 422 自動返却（Enum 違反）
```

---

## S3 / SQS エラー

インフラ層で発生した例外は service 層に伝播させ、service 層から HTTPException に変換する。

```python
# app/services/generation/dalle.py
async def generate(self, req: GenerateRequest) -> GenerateResponse:
    try:
        s3_key = await self._s3.upload_from_url(url=image_url, key=...)
    except Exception as e:
        logger.error("S3 upload failed job_id=%s: %s", req.job_id, e)
        raise HTTPException(status_code=500, detail="Storage upload failed")
```

---

## DB エラー

asyncpg の例外はキャッチして HTTPException に変換する。

```python
async def get_job_status(job_id: UUID) -> JobStatusResponse:
    pool = await get_pool()
    try:
        row = await pool.fetchrow("SELECT ... WHERE id = $1", job_id)
    except asyncpg.PostgresConnectionError as e:
        logger.error("DB connection error: %s", e)
        raise HTTPException(status_code=503, detail="Database unavailable")

    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")
```

---

## ログ出力規則

| 状況 | ログレベル | 含めるフィールド |
|---|---|---|
| 処理開始 | `INFO` | `job_id`, `user_id`, 処理名 |
| 処理完了 | `INFO` | `job_id`, `s3_key` 等の結果 |
| 外部 API エラー | `ERROR` | `job_id`, エラーメッセージ |
| DB エラー | `ERROR` | エラーメッセージ |
| デバッグ情報 | `DEBUG` | 詳細パラメータ |

```python
logger.info("DALL-E 3 generation start job_id=%s", req.job_id)
logger.info("DALL-E 3 generation done job_id=%s s3_key=%s", req.job_id, s3_key)
logger.error("DALL-E generation failed job_id=%s: %s", req.job_id, e)
```

- **プロンプトの全文はログに残さない**（プライバシー・コスト上の理由）
- `logger = logging.getLogger(__name__)` でモジュールごとにロガーを取得する

---

## エラーメッセージのルール

- 英語・先頭大文字・ピリオドなし
- リソース名を含める場合は単数形

```
"Job not found"          ← 何が見つからないかを示す
"Forbidden"              ← 認証エラー
"Image generation failed"  ← 何が失敗したかを示す
"Storage upload failed"  ← ストレージ操作の失敗
```

---

## ハンドラー層のルール

### Pydantic の自動バリデーションに任せる

手動でリクエストをバリデーションしない。

```python
# 正：FastAPI が自動バリデーション
@router.post("/generate", response_model=GenerateResponse)
async def generate_thumbnail(req: GenerateRequest) -> GenerateResponse:
    return await _dalle.generate(req)

# 誤：手動チェックは不要
@router.post("/generate")
async def generate_thumbnail(req: GenerateRequest):
    if not req.prompt:
        raise HTTPException(status_code=400, detail="prompt is required")
```

### err.Error() 相当の情報をレスポンスに含めない

```python
# 正：汎用メッセージのみ
raise HTTPException(status_code=500, detail="Image generation failed")

# 誤：内部エラーが漏れる
raise HTTPException(status_code=500, detail=str(e))
```
