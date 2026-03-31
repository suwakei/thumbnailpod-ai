# アーキテクチャ規則

## 層の責務を守る

| 層 | 場所 | やること | やらないこと |
|---|---|---|---|
| API 層 | `app/api/internal/` | Pydantic 変換、認証 Depends、サービス呼び出し | ビジネスロジック、DB 操作 |
| Service 層 | `app/services/` | AI 処理、外部 API 呼び出し | HTTP ステータスコードの決定（原則 HTTPException は OK） |
| Infrastructure 層 | `app/infrastructure/` | DB・S3・SQS の具体操作 | ビジネスロジック |
| Schema 層 | `app/schemas/` | Pydantic モデル定義 | ロジック |
| Core 層 | `app/core/` | 設定・認証・ログ | ビジネスロジック |

---

## 認証は Depends で適用する

個別のハンドラーに認証ロジックを書かない。
ルーターレベルで `dependencies=` を使って一括適用する。

```python
# 正
router = APIRouter(dependencies=[Depends(verify_internal_secret)])

# 誤：ハンドラーごとに書く
@router.post("/generate")
async def generate(req: GenerateRequest, _: None = Depends(verify_internal_secret)):
    ...
```

---

## サービスはシングルトン

サービスインスタンスをリクエストごとに生成しない。
モジュールレベルで一度だけ生成する。

```python
# 正：モジュールレベルシングルトン
_dalle = DalleService()
_sdxl = StableDiffusionService()

@router.post("/generate")
async def generate_thumbnail(req: GenerateRequest) -> GenerateResponse:
    return await _dalle.generate(req)

# 誤：リクエストごとに生成
@router.post("/generate")
async def generate_thumbnail(req: GenerateRequest) -> GenerateResponse:
    service = DalleService()  # 毎回生成しない
    return await service.generate(req)
```

---

## response_model を必ず指定する

FastAPI のハンドラーには `response_model=` を必ず指定する。
Pydantic による自動シリアライズ・バリデーションを活用する。

```python
# 正
@router.post("/generate", response_model=GenerateResponse)
async def generate_thumbnail(req: GenerateRequest) -> GenerateResponse:
    ...

# 誤：response_model なし
@router.post("/generate")
async def generate_thumbnail(req: GenerateRequest):
    return {"job_id": ..., "s3_key": ...}
```

---

## GPU 処理はスレッドプールに委譲する

GPU/CPU バウンドな処理（torch 推論・SAM・psd-tools）は `run_in_executor` でラップする。
async 関数内で直接同期的な重い処理を呼び出さない。

```python
# 正
loop = asyncio.get_event_loop()
image = await loop.run_in_executor(None, self._run_inference, req)

# 誤：イベントループをブロック
image = self._run_inference(req)  # async 関数内で同期ブロック
```

---

## 設定は settings から取得する

環境変数・設定値はコードにハードコードせず、`app.core.config.settings` から取得する。

```python
# 正
from app.core.config import settings
pipe = StableDiffusionXLPipeline.from_pretrained(settings.sd_model_id, ...)

# 誤：ハードコード
pipe = StableDiffusionXLPipeline.from_pretrained("stabilityai/stable-diffusion-xl-base-1.0", ...)
```

---

## データベースは infrastructure 層にのみ書く

DB 操作は `app/infrastructure/database.py` に集約する。
Service 層から直接 asyncpg を使わない。

```python
# 正：infrastructure 層を呼ぶ
from app.infrastructure.database import update_job_status
await update_job_status(job_id, JobStatus.COMPLETED)

# 誤：サービス層で直接 DB 操作
pool = await asyncpg.create_pool(...)
await pool.execute("UPDATE generation_jobs ...", ...)
```
