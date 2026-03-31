# API 設計規則

## ベース URL・バージョニング

```
/internal/{resource}
```

- このサービスは **内部専用（VPC 内部）** のため、バージョニングはパスに含めない
- Go バックエンドが唯一の呼び出し元であり、バージョンアップは両サービスを同時にデプロイする
- ヘルスチェックのみバージョン外に置く（`/health`）

---

## 認証

すべての `/internal/*` エンドポイントは `X-Internal-Secret` ヘッダーが必須。

```
X-Internal-Secret: <共有シークレット>
```

- ルーターレベルで `dependencies=[Depends(verify_internal_secret)]` を適用
- シークレット不一致 → `403 Forbidden`
- ヘッダー未設定 → `403 Forbidden`（`auto_error=False` で明示的にチェック）

---

## リソース命名

| ルール | 正 | 誤 |
|---|---|---|
| snake_case（小文字・アンダースコア） | `/internal/generate` | `/internal/generateThumbnail` |
| 名詞ベース | `/internal/segment` | `/internal/doSegment` |
| 階層は親子関係のみ | `/internal/style/analyze` | `/internal/style/analysis/run` |

---

## HTTP メソッド

| メソッド | 用途 | 例 |
|---|---|---|
| `POST` | AI 処理の実行（非冪等） | `POST /internal/generate` |
| `GET` | 状態の取得（冪等） | `GET /internal/jobs/{job_id}` |

---

## リクエスト Schema（Pydantic）

### 命名・構造ルール

- クラス名は PascalCase + `Request` サフィックス
- フィールド名は snake_case
- 必須フィールドは `= Field(...)` または型アノテーションのみ
- オプショナルは `| None = None`
- バリデーション制約は `Field` で付与する

```python
class GenerateRequest(BaseModel):
    job_id: UUID
    user_id: UUID
    prompt: str = Field(..., min_length=1, max_length=2000)
    engine: GenerationEngine = GenerationEngine.DALLE3
    style_model_id: UUID | None = None
    negative_prompt: str | None = None
    width: int = 1280
    height: int = 720
```

---

## レスポンス Schema（Pydantic）

### 命名・構造ルール

- クラス名は PascalCase + `Response` サフィックス
- フィールド名は snake_case
- `response_model=` にレスポンス型を指定することで自動シリアライズ

```python
class GenerateResponse(BaseModel):
    job_id: UUID
    s3_key: str
    width: int
    height: int
```

### ハンドラーでの指定方法

```python
@router.post("/generate", response_model=GenerateResponse)
async def generate_thumbnail(req: GenerateRequest) -> GenerateResponse:
    ...
```

---

## HTTP ステータスコード

| コード | 用途 |
|---|---|
| `200 OK` | 処理成功（GET・POST とも） |
| `403 Forbidden` | 認証失敗（X-Internal-Secret 不一致） |
| `404 Not Found` | 対象リソースが存在しない |
| `422 Unprocessable Entity` | Pydantic バリデーションエラー（自動） |
| `500 Internal Server Error` | 予期しないサーバーエラー |

---

## エラーレスポンス

FastAPI の `HTTPException` を使い、フォーマットを統一する。

```python
raise HTTPException(status_code=404, detail="Job not found")
raise HTTPException(status_code=403, detail="Forbidden")
```

FastAPI が自動的に以下の JSON を生成する：

```json
{ "detail": "Job not found" }
```

### エラーメッセージのルール

- 英語・先頭大文字・ピリオドなし
- ユーザーに原因が伝わる内容にする（内部の詳細は含めない）
- Pydantic バリデーションエラー（422）はフレームワークが自動生成するためハンドラー側で処理不要

---

## パスパラメータ

- snake_case を使う
- UUID を受け取る場合は FastAPI が自動でパース・検証する（型アノテーションに `UUID` を指定）

```python
@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job(job_id: UUID) -> JobStatusResponse:
    # job_id は FastAPI が UUID として自動パース
    # 無効な UUID → 422 Unprocessable Entity が自動返却
    return await get_job_status(job_id)
```

---

## Enum フィールド

`StrEnum` で定義した Enum をフィールドに使うと、Pydantic が自動でバリデーションする。

```python
class GenerationEngine(StrEnum):
    DALLE3 = "dalle3"
    SDXL   = "sdxl"

class GenerateRequest(BaseModel):
    engine: GenerationEngine = GenerationEngine.DALLE3
    # "dalle3" / "sdxl" 以外の値 → 422 自動返却
```

---

## エンドポイント一覧

| メソッド | パス | 認証 | ハンドラー | 説明 |
|---|---|---|---|---|
| `GET` | `/health` | 不要 | `main.health` | ヘルスチェック |
| `POST` | `/internal/generate` | 要 | `generate.generate_thumbnail` | サムネイル生成 |
| `POST` | `/internal/style/analyze` | 要 | `style.analyze_style` | スタイル解析 |
| `POST` | `/internal/style/train` | 要 | `style.train_style` | 学習ジョブキューイング |
| `POST` | `/internal/segment` | 要 | `segment.segment_image` | SAM セグメンテーション |
| `POST` | `/internal/psd` | 要 | `psd.build_psd` | PSD 組み立て |
| `GET` | `/internal/jobs/{job_id}` | 要 | `jobs.get_job` | ジョブステータス取得 |
