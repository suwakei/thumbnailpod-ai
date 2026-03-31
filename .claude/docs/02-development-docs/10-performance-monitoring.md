# パフォーマンス監視

## ログ設計

`app/core/logging.py` で structlog または標準 logging を設定する。

### ログレベルの使い分け

| レベル | 用途 |
|---|---|
| `INFO` | 処理開始・完了（`job_id`, `user_id` を含める） |
| `DEBUG` | S3 アップロード完了・DB クエリ詳細 |
| `ERROR` | 外部 API エラー・DB エラー |
| `WARNING` | リトライ・パフォーマンス劣化の予兆 |

### ログフォーマット例

```python
# 処理開始（INFO）
logger.info("DALL-E 3 generation start job_id=%s", req.job_id)

# 処理完了（INFO）
logger.info("DALL-E 3 generation done job_id=%s s3_key=%s", req.job_id, s3_key)

# S3 操作（DEBUG）
logger.debug("Uploaded s3://%s/%s", settings.s3_bucket, key)

# DB 操作（DEBUG）
logger.debug("Job %s status -> %s", job_id, status)

# エラー（ERROR）
logger.error("DALL-E generation failed job_id=%s: %s", req.job_id, e)
```

---

## ヘルスチェック

```python
@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
```

ECS の ALB ヘルスチェックが `/health` を定期的に呼び出す。
将来的には DB 接続確認・GPU メモリ使用率を含めることを検討する。

---

## ECS メトリクス

| メトリクス | 監視内容 | アラート閾値（目安） |
|---|---|---|
| CPU 使用率 | SDXL・SAM 推論負荷 | > 80% が 5 分継続 |
| GPU メモリ使用率 | SDXL・SAM のモデルロード | > 90% |
| タスク数 | スケールアウト判断 | キュー深度 > 10 |
| エラー率 | 5xx レスポンス割合 | > 1% |

---

## SQS キュー監視

スタイル学習ジョブは SQS 経由で AI Worker に委譲される。

| メトリクス | 説明 |
|---|---|
| `ApproximateNumberOfMessages` | 未処理ジョブ数 |
| `ApproximateAgeOfOldestMessage` | 最古メッセージの滞留時間 |

滞留時間が長い場合は AI Worker のスケールアウトを検討する。

---

## ログ収集

ECS の CloudWatch Logs ドライバーを使い、コンテナログを CloudWatch Logs に転送する。

- ロググループ: `/ecs/thumbnailai-ai-service`
- ログ保持期間: 30 日
- フィルター: `ERROR` 以上を CloudWatch アラームに設定
