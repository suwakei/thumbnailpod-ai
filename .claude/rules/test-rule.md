# テスト規則

## 外部サービスは必ずモックする

テスト環境で OpenAI API・S3・SQS・DB に実際にアクセスしない。
モジュールレベルのシングルトンは `unittest.mock.patch` でモックする。

```python
from unittest.mock import AsyncMock, patch

def test_generate(client, internal_headers):
    with patch("app.api.internal.generate._dalle") as mock:
        mock.generate = AsyncMock(return_value=GenerateResponse(...))
        response = client.post("/internal/generate", json={...}, headers=internal_headers)
    assert response.status_code == 200
```

---

## 認証テストを必ず書く

すべての `/internal/*` エンドポイントに対して「認証なしで 403 になること」を確認するテストを書く。

```python
def test_endpoint_requires_auth(client):
    response = client.post("/internal/generate", json={...})
    assert response.status_code == 403
```

---

## バリデーションエラーのテストを書く

422 が返るケース（無効な Enum 値・空文字・範囲外など）も確認する。

```python
def test_invalid_engine(client, internal_headers):
    response = client.post(
        "/internal/generate",
        json={"engine": "unknown"},
        headers=internal_headers,
    )
    assert response.status_code == 422
```

---

## 非同期メソッドは AsyncMock を使う

`async def` メソッドのモックには `AsyncMock` を使う。
通常の `MagicMock` では `await` できない。

```python
# 正
mock.generate = AsyncMock(return_value=expected_response)

# 誤
mock.generate = MagicMock(return_value=expected_response)
```

---

## TestClient は同期的に使う

FastAPI の `TestClient` は同期的に動作するため、テスト関数は通常の `def` で書く。

```python
# 正
def test_generate_success(client, internal_headers):
    response = client.post(...)
    assert response.status_code == 200
```

---

## conftest.py の環境変数設定

`conftest.py` でのテスト環境変数設定は `import app.*` より前に行う。
Pydantic Settings がモジュールロード時に環境変数を読み込むため。

```python
# conftest.py の先頭
import os
os.environ.setdefault("INTERNAL_API_SECRET", "test-secret")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
```

---

## モックのパスは「使っている場所」を指定する

`patch` のパスは、モックしたいオブジェクトが **使われているモジュール** のパスを指定する。

```python
# 正：generate.py で _dalle を使っているので
with patch("app.api.internal.generate._dalle") as mock:
    ...
```
