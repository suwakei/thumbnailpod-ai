# テスト戦略

## 基本方針

- **外部サービスはモック**する（OpenAI・S3・SQS・DB）
- テストは **`TestClient`** を使った HTTP レベルのテストを中心に書く
- CI で実行されるテストは外部への実際のアクセスを行わない
- テストファイルは `tests/api/test_{機能}.py` に配置する

---

## テストの種類

| 種類 | 内容 | 場所 |
|---|---|---|
| API テスト | ハンドラーの HTTP 入出力・認証検証 | `tests/api/test_*.py` |
| サービステスト | AI 処理ロジックのユニットテスト | `tests/services/test_*.py`（未作成） |

現在は API テストが主体。サービステストは必要に応じて追加する。

---

## フィクスチャ（conftest.py）

`tests/conftest.py` に共通フィクスチャを定義する。

```python
@pytest.fixture(scope="session")
def client():
    from app.main import app
    return TestClient(app)

@pytest.fixture
def internal_headers():
    return {"X-Internal-Secret": "test-secret"}

@pytest.fixture
def sample_job_id():
    return str(uuid.uuid4())

@pytest.fixture
def sample_user_id():
    return str(uuid.uuid4())
```

### 環境変数の設定

テスト実行時に必要な環境変数を `conftest.py` の先頭（import より前）に設定する。

```python
import os
os.environ.setdefault("INTERNAL_API_SECRET", "test-secret")
os.environ.setdefault("OPENAI_API_KEY", "sk-test")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
os.environ.setdefault("S3_BUCKET", "test-bucket")
os.environ.setdefault("SQS_QUEUE_URL", "http://localhost:4566/test/queue")
```

---

## 外部サービスのモック

サービスインスタンスはモジュールレベルのシングルトンのため、`unittest.mock.patch` でモックする。

```python
from unittest.mock import AsyncMock, patch

def test_generate_dalle_success(client, internal_headers, sample_job_id, sample_user_id):
    expected = GenerateResponse(
        job_id=sample_job_id,
        s3_key=f"thumbnails/{sample_user_id}/{sample_job_id}.png",
        width=1280,
        height=720,
    )
    with patch("app.api.internal.generate._dalle") as mock:
        mock.generate = AsyncMock(return_value=expected)
        response = client.post(
            "/internal/generate",
            json={
                "job_id": sample_job_id,
                "user_id": sample_user_id,
                "prompt": "YouTube thumbnail",
                "engine": "dalle3",
            },
            headers=internal_headers,
        )
    assert response.status_code == 200
    assert response.json()["job_id"] == sample_job_id
```

- 非同期メソッドは `AsyncMock` を使う
- モックのパスはモジュールが **使っている場所**（`app.api.internal.generate._dalle`）を指定する

---

## 認証テスト

すべてのエンドポイントで認証が必要なことを確認するテストを書く。

```python
def test_generate_requires_auth(client, sample_job_id, sample_user_id):
    # ヘッダーなし → 403
    response = client.post(
        "/internal/generate",
        json={"job_id": sample_job_id, "user_id": sample_user_id, "prompt": "test"},
    )
    assert response.status_code == 403
```

---

## バリデーションテスト

Pydantic バリデーションが正しく動作していることを確認する。

```python
def test_generate_invalid_engine(client, internal_headers, sample_job_id, sample_user_id):
    response = client.post(
        "/internal/generate",
        json={"job_id": sample_job_id, "user_id": sample_user_id,
              "prompt": "test", "engine": "unknown_engine"},
        headers=internal_headers,
    )
    assert response.status_code == 422

def test_generate_empty_prompt(client, internal_headers, sample_job_id, sample_user_id):
    response = client.post(
        "/internal/generate",
        json={"job_id": sample_job_id, "user_id": sample_user_id, "prompt": ""},
        headers=internal_headers,
    )
    assert response.status_code == 422
```

---

## pytest 設定

`pyproject.toml` で設定する。

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

`asyncio_mode = "auto"` により、`async def test_*` 関数を自動的に非同期テストとして実行する。

---

## テスト実行

```bash
# 全テスト実行
pytest tests/ -v

# 特定ファイルのみ
pytest tests/api/test_generate.py -v

# 失敗時に即停止
pytest tests/ -x

# 短縮トレースバック
pytest tests/ --tb=short
```

---

## CI でのテスト実行

`.github/workflows/ci.yml` でテストを実行する。

```yaml
- name: Run tests
  env:
    ENV: test
    INTERNAL_API_SECRET: test-secret
    OPENAI_API_KEY: sk-test
    DATABASE_URL: postgresql://thumbnailai:thumbnailai@localhost:5432/thumbnailai
    S3_BUCKET: test-bucket
    SQS_QUEUE_URL: http://localhost:4566/test/queue
  run: pytest tests/ -v --tb=short
```

CI では PostgreSQL サービスコンテナが起動しているため、マイグレーションも実行される（ただし AI サービスの API テストは DB アクセスをモックする）。

---

## テストを書く際の注意

- モジュールレベルのシングルトン（`_dalle`, `_sdxl` 等）は `patch` でモックする
- `TestClient` は同期的に動作するため、`async def test_*` にする必要はない
- レスポンスの `assert` では必要最低限のフィールドのみ検証する（実装変更に強くするため）
