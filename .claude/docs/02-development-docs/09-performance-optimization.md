# パフォーマンス最適化

## GPU メモリ管理

### 遅延ロード（Lazy Loading）

重いモデル（SDXL・SAM・CLIP）はコンテナ起動時にロードせず、**初回リクエスト時にロード**する。
これによりコンテナ起動時間を短縮し、モデルが不要な場合のメモリ消費を抑える。

```python
class StableDiffusionService:
    def __init__(self) -> None:
        self._pipe = None  # 起動時はロードしない

    def _load_pipeline(self):
        from diffusers import StableDiffusionXLPipeline
        import torch

        if self._pipe is None:  # 一度だけロード
            self._pipe = StableDiffusionXLPipeline.from_pretrained(
                settings.sd_model_id,
                torch_dtype=torch.float16,  # fp16 でメモリ節約
                use_safetensors=True,
            ).to("cuda")
        return self._pipe
```

### モデルの保持

モデルはモジュールレベルのシングルトンサービスに保持する。
リクエストごとに新しいインスタンスを作成しない。

---

## 非同期処理とブロッキング操作

### asyncio.run_in_executor の使用

PyTorch 推論・SAM・psd-tools など CPU/GPU バウンドな処理は `run_in_executor` でスレッドプールに委譲する。
イベントループを直接ブロックしない。

```python
loop = asyncio.get_event_loop()
image = await loop.run_in_executor(None, self._run_inference, req)
```

### httpx 非同期クライアント

画像取得など HTTP リクエストはすべて `httpx.AsyncClient` で行う。
`requests` ライブラリ（同期）は使わない。

---

## DB 接続プール

asyncpg の接続プールを使い、リクエストごとに接続を生成しない。

```python
_pool = await asyncpg.create_pool(
    settings.database_url,
    min_size=2,   # 常時 2 接続を維持（ウォームアップ済み）
    max_size=10,  # 最大 10 並列接続
)
```

---

## SDXL 推論パラメータ

`num_inference_steps=30` は品質と推論時間のバランスポイント。
品質重視なら 50、速度重視なら 20 に調整する。

---

## CLIP 埋め込みのバッチ処理

複数画像は一括でバッチ処理する。1枚ずつループで処理しない。

```python
inputs = processor(images=images, return_tensors="pt", padding=True)
with torch.no_grad():
    features = model.get_image_features(**inputs)
mean_embedding = features.mean(dim=0)
```

---

## S3 アップロード

画像は PIL.Image から BytesIO 経由でメモリに保存して S3 へ直接アップロードする。
ディスクへの書き込みを挟まない。

```python
buf = BytesIO()
image.save(buf, format="PNG")
await self.upload_bytes(data=buf.getvalue(), key=key, content_type="image/png")
```
