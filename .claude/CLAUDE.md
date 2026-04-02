## 設計書リファレンス — 実装・レビュー・設計判断の前に参照すること

cat > ~/thumbnailpod/thumbnailpod-ai/CLAUDE.md << 'EOF'
# ThumbnailPod — AI Service (Python + FastAPI, AWS ECS Fargate + GPU)

## 責務
画像生成の頭脳。スタイル分析・モデル学習・画像生成・レイヤー分離・編集適用。
thumbnailpod-back からのみ呼ばれる内部サービス。

## デプロイ
AWS ECS Fargate（GPU インスタンス、private subnet）。
back からのみアクセス可能（内部 ALB or サービスディスカバリ）。
Terraform で管理（infra/modules/ecs-ai）。

## ディレクトリ構造
app/
├── main.py                     # FastAPI + ルーター登録
├── api/
│   ├── generate.py             # POST /ai/generate
│   ├── analyze.py              # POST /ai/analyze
│   ├── edit.py                 # POST /ai/edit（編集適用）
│   └── models.py               # GET  /ai/models/:id
├── services/
│   ├── style_analyzer.py       # サムネイル分析
│   ├── generator.py            # 画像生成パイプライン
│   ├── layer_separator.py      # レイヤー分離
│   ├── editor.py               # 編集パラメータ → レイヤー再合成
│   └── model_manager.py        # スタイルモデル保存・読み込み
├── models/                     # Pydantic スキーマ
│   ├── generate.py
│   ├── analyze.py
│   └── edit.py                 # EditRequest / EditResponse
├── core/
│   ├── config.py               # 環境変数
│   └── storage.py              # S3 操作
└── ml/
    ├── pipelines/              # 画像生成パイプライン
    └── weights/                # モデルウェイト

## API エンドポイント

### POST /ai/generate
画像生成 + レイヤー分離。
入力: model_id, text_content, composition, options
出力: layers (各レイヤーの S3 URL), metadata

### POST /ai/analyze
スタイル分析 + モデル学習。
入力: image_urls[]
出力: model_id, analysis (colors, layout, font, elements)

### POST /ai/edit
編集パラメータを受け取り、該当レイヤーを変換して再合成。
入力: original_layers (各レイヤーの S3 URL), operations[]
出力: updated_layers (更新されたレイヤーの S3 URL)
```json
// Request
{
  "original_layers": {
    "composite": "s3://...",
    "text_layer": "s3://...",
    "person_layer": "s3://...",
    "background_layer": "s3://...",
    "effect_layer": "s3://..."
  },
  "operations": [
    {"type": "text_change", "layer": "text_layer", "content": "新テキスト", "position": {"x": 100, "y": 50}},
    {"type": "color_adjust", "layer": "background_layer", "brightness": 1.2}
  ]
}
// Response
{
  "layers": {
    "composite": "s3://xxx/edited_composite.png",
    "text_layer": "s3://xxx/edited_text.png",
    "background_layer": "s3://xxx/edited_background.png"
  },
  "unchanged_layers": ["person_layer", "effect_layer"]
}
```

### GET /ai/models/:id
モデル状態確認。status: training / ready / failed

## レイヤー定義
| レイヤー | 内容 | 形式 |
|---------|------|------|
| composite | 合成済み最終画像 | PNG |
| text_layer | テキスト要素（透過） | PNG |
| person_layer | 人物切り抜き（透過） | PNG |
| background_layer | 背景 | PNG |
| effect_layer | エフェクト・装飾（透過） | PNG |

## 編集処理の方針
- 変更があったレイヤーのみ再生成（差分更新）
- 変更のないレイヤーは unchanged_layers で返し、back はそのまま保持
- 最終的に全レイヤーを composite に再合成

## 環境変数
- AWS_S3_BUCKET
- MODEL_STORAGE_PATH
- MAX_CONCURRENT_JOBS（GPU メモリ制限のため同時実行数制限）
EOF

設計に関わるタスク（実装・バグ修正・レビュー・新機能追加）では、作業開始前に `.claude/docs/` 配下の該当設計書を確認すること。
コードだけから読み取れない意図・制約・命名規則がドCLAUDEキュメントに記載されている。

| 使用する場面 | 参照すべきドキュメント |
|---|---|
| ルーティング・ハンドラー・レスポンス形式・ステータスコードの判断に迷ったとき | `.claude/docs/02-development-docs/03-api-design.md` |                                                    
| テーブル設計・SQL・マイグレーション・インデックスの追加や変更をするとき | `.claude/docs/02-development-docs/02-database-design.md` |                                                    
| 層をまたぐ実装・DI・非同期フロー・インフラ構成を把握したいとき | `.claude/docs/02-development-docs/01-architecture-design.md` |                                                         
| エラーを返す・ラップする・HTTP に変換する実装をするとき | `.claude/docs/02-development-docs/04-error-handling.md` |                                                                     
| 型・enum・定数・struct・interface を新たに定義するとき | `.claude/docs/02-development-docs/05-type-definition.md` |                                                                     
| テストを追加・修正するとき、またはテスト戦略を確認したいとき | `.claude/docs/02-development-docs/06-test-strategy.md` |                                                                 
| 認証・認可・トークン・外部入力に関わる実装をするとき | `.claude/docs/02-development-docs/08-security-design.md` |                                                                       
| このプロジェクトが何をするサービスか・全体像を把握したいとき | `.claude/docs/01-project-overview/01-thumbnailpod-backend-concept.md` |
| CI/CD ワークフロー・デプロイフロー・GitHub Actions を変更・理解したいとき | `.claude/docs/02-development-docs/07-cicd-design.md` |   

## ワークフロー・オーケストレーション — 計画モード・サブエージェント・自己改善・検証・洗練さ・バグ修正のルール
@.claude/WORKFLOW.md

## タスク管理 — todo.md / lessons.md の運用ルール
@.claude/TASKS.md

## 基本原則 — シンプルさ・怠慢禁止・最小限の影響
@.claude/PRINCIPLES.md
