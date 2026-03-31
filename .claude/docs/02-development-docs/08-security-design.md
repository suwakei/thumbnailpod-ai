# セキュリティ設計

## 基本方針

- このサービスは **VPC 内部専用**（インターネットから直接アクセス不可）
- Go バックエンドのみが唯一の呼び出し元
- 認証は `X-Internal-Secret` ヘッダーによる共有シークレット方式
- ユーザーの JWT トークンはこのサービスに到達しない（Go バックエンドで処理済み）

---

## 内部認証（X-Internal-Secret）

### 実装

```python
# app/core/security.py
from fastapi.security import APIKeyHeader

_api_key_header = APIKeyHeader(name="X-Internal-Secret", auto_error=False)

async def verify_internal_secret(api_key: str = Security(_api_key_header)) -> None:
    """Verify that the request comes from the Go API (VPC internal shared secret)."""
    if api_key != settings.internal_api_secret:
        raise HTTPException(status_code=403, detail="Forbidden")
```

### 適用方法

ルーターレベルで全エンドポイントに一括適用する。

```python
router = APIRouter(dependencies=[Depends(verify_internal_secret)])
```

### シークレット管理

- 本番環境: AWS Secrets Manager または ECS タスク定義の環境変数（暗号化）
- 開発環境: `.env` ファイル（`.gitignore` に含める）
- CI: GitHub Actions シークレット

---

## VPC 内部通信

```
Internet
  │
  ▼
ALB（Go バックエンド）← TLS 終端
  │
  │  VPC 内部（HTTP、TLS 不要）
  ▼
AI Service（このサービス）
```

- AI Service は **パブリックサブネットに置かない**
- セキュリティグループで Go バックエンド ECS タスクからのみ受信許可

---

## 入力バリデーション

Pydantic の自動バリデーションで XSS・インジェクション対策を行う。

```python
class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000)
    # 最大長を設定してバッファオーバーフロー・LLM プロンプトインジェクションを緩和
```

### SQL インジェクション対策

asyncpg のパラメータプレースホルダを使う。文字列結合は禁止。

```python
# 正
await pool.fetchrow("SELECT * FROM generation_jobs WHERE id = $1", job_id)

# 誤（禁止）
await pool.fetchrow(f"SELECT * FROM generation_jobs WHERE id = '{job_id}'")
```

---

## ログのセキュリティ

| ログに含めてよいもの | ログに含めてはいけないもの |
|---|---|
| `job_id`, `user_id` | プロンプトの全文 |
| 処理ステータス | 画像データ（バイナリ） |
| S3 キー（パス） | `INTERNAL_API_SECRET` |
| エラー種別 | `OPENAI_API_KEY` |
| 処理時間 | ユーザーの個人情報 |

```python
# 正
logger.info("DALL-E 3 generation start job_id=%s", req.job_id)

# 誤
logger.info("Generation start prompt=%s", req.prompt)  # プロンプトは含めない
logger.debug("API key=%s", settings.openai_api_key)    # 秘密鍵は絶対に含めない
```

---

## 環境変数の保護

- `.env` ファイルは `.gitignore` に追加する（`.env.example` のみコミット）
- `.claude/settings.json` で `Read(.env*)` を deny リストに追加済み
- 本番環境では環境変数を ECS タスク定義またはシークレットマネージャーで注入する

---

## OpenAI API キー

- `OPENAI_API_KEY` は環境変数経由でのみ渡す
- コードにハードコードしない
- ログに出力しない
- テスト環境では `sk-test` 等のダミー値を使い、実際の API を呼び出さない

---

## 依存ライブラリの脆弱性スキャン

```bash
# pip-audit で既知の脆弱性をスキャン
pip-audit -r requirements.txt
```

`.claude/hooks/vuln.sh` に組み込んで定期実行する。
