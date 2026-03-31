# アーキテクチャ設計

## 基本構成

FastAPI による **レイヤード・アーキテクチャ**。依存方向は `api → services → infrastructure`。

```
app/
├── main.py                   # アプリ初期化・ルーター登録
├── api/
│   └── internal/             # HTTP ハンドラー層（リクエスト/レスポンス変換・認証）
│       ├── generate.py       # POST /internal/generate
│       ├── style.py          # POST /internal/style/analyze・train
│       ├── segment.py        # POST /internal/segment
│       ├── psd.py            # POST /internal/psd
│       └── jobs.py           # GET /internal/jobs/{job_id}
├── core/
│   ├── config.py             # pydantic-settings による設定管理
│   ├── security.py           # X-Internal-Secret ヘッダー検証（Depends）
│   └── logging.py            # ログ設定
├── schemas/                  # Pydantic リクエスト/レスポンスモデル
│   ├── generate.py
│   ├── style.py
│   ├── segment.py
│   ├── psd.py
│   └── job.py
├── services/                 # ビジネスロジック・AI 処理層
│   ├── generation/
│   │   ├── dalle.py          # DALL-E 3 生成
│   │   └── stable_diffusion.py  # SDXL 推論
│   ├── style/
│   │   ├── analyzer.py       # CLIP スタイル解析
│   │   └── trainer.py        # SQS へのトレーニングジョブキューイング
│   ├── segment/
│   │   └── sam.py            # SAM セグメンテーション
│   └── psd/
│       └── builder.py        # PSD ファイル組み立て
└── infrastructure/           # 外部システムクライアント
    ├── database.py           # asyncpg 接続プール・SQL 操作
    ├── s3.py                 # aioboto3 S3 クライアント
    └── sqs.py                # aioboto3 SQS クライアント
```

---

## 各層の責務

| 層 | 場所 | 責務 |
|---|---|---|
| API 層 | `app/api/internal/` | HTTP 入出力変換、認証 Depends 適用、サービス呼び出し |
| Schema 層 | `app/schemas/` | Pydantic によるリクエスト/レスポンス型定義 |
| Service 層 | `app/services/` | AI 処理・ビジネスロジック・外部 API 呼び出し |
| Infrastructure 層 | `app/infrastructure/` | DB・S3・SQS の具体実装 |
| Core 層 | `app/core/` | 設定・認証・ログの横断的関心事 |

---

## 依存性注入（Depends）

認証は FastAPI の `Depends` で全エンドポイントルーターに適用する。

```python
# app/core/security.py
_api_key_header = APIKeyHeader(name="X-Internal-Secret", auto_error=False)

async def verify_internal_secret(api_key: str = Security(_api_key_header)) -> None:
    if api_key != settings.internal_api_secret:
        raise HTTPException(status_code=403, detail="Forbidden")

# app/api/internal/generate.py
router = APIRouter(dependencies=[Depends(verify_internal_secret)])
```

ルーターレベルで `dependencies=` を指定することで、全ルートに一括適用する。
個別のハンドラーに `Depends` を書かない。

---

## サービスのインスタンス化

重いモデル（SDXL・SAM・CLIP）はコンテナ起動時にロードせず、**初回リクエスト時に遅延ロード**する。
サービスインスタンスはモジュールレベルのシングルトンとして保持し、リクエストごとに生成しない。

```python
# app/api/internal/generate.py
_dalle = DalleService()   # モジュールロード時にインスタンス化（モデルはまだロードしない）
_sdxl = StableDiffusionService()

@router.post("/generate")
async def generate_thumbnail(req: GenerateRequest) -> GenerateResponse:
    if req.engine == GenerationEngine.DALLE3:
        return await _dalle.generate(req)   # ← 内部で必要になったときにロード
    return await _sdxl.generate(req)
```

---

## GPU / CPU ブロッキング処理

PyTorch・SAM・psd-tools などの CPU/GPU バウンドな処理は `asyncio.run_in_executor` でスレッドプールに委譲し、イベントループをブロックしない。

```python
loop = asyncio.get_event_loop()
result = await loop.run_in_executor(None, self._run_inference, req)
```

---

## リクエストのライフサイクル

```
HTTP リクエスト（Go API → VPC 内部）
  │
  ▼
FastAPI ルーター
  │
  ▼
Depends(verify_internal_secret)  ← X-Internal-Secret ヘッダー検証
  │ 403 Forbidden（不正）
  ▼
ハンドラー（Pydantic バリデーション済みリクエスト受け取り）
  │ 422 Unprocessable Entity（バリデーション失敗）
  ▼
Service（AI 処理 / 外部 API 呼び出し）
  │
  ▼
Infrastructure（S3 / SQS / DB）
  │
  ▼
ハンドラー（Pydantic レスポンスモデルで返却）
```

---

## 非同期処理フロー

### 画像生成（同期処理）

```
POST /internal/generate
  │
  ├─ 1. Pydantic バリデーション
  ├─ 2. エンジン分岐（dalle3 / sdxl）
  ├─ 3. 画像生成（API 呼び出し or GPU 推論）
  ├─ 4. S3 に画像アップロード（s3_key 取得）
  └─ 5. GenerateResponse 返却（s3_key, width, height）
```

### スタイル学習（非同期 / SQS）

```
POST /internal/style/train
  │
  ├─ 1. SQS に訓練ジョブメッセージ送信
  │       { task: "style_train", job_id, style_model_id, image_urls, phase }
  └─ 2. StyleTrainResponse 返却（job_id のみ）

  [AI Worker（別 ECS タスク）]
  ├─ SQS メッセージを消費
  ├─ LoRA / ControlNet 学習実行
  └─ style_models.status を ready / failed に更新
```

---

## インフラ構成（AWS）

```
VPC 内部
  │
  ├── AI Service（ECS Fargate）  ← このアプリ（:8000）
  │     ├── S3（thumbnails/ layers/ PSD）
  │     └── SQS（style_train ジョブキュー）
  │
  └── AI Worker（ECS Task）  ← 重い学習処理
        └── S3（LoRA モデル保存）
```

---

## ローカル開発環境構成

```
docker-compose.yml
  ├── ai-service  FastAPI（:8000）
  ├── postgres    PostgreSQL 15（:5432）
  └── localstack  S3 / SQS エミュレータ（:4566）
```

`AWS_ENDPOINT_URL=http://localhost:4566` で LocalStack に接続する。
