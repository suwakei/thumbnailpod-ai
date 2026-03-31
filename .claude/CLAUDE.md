## 設計書リファレンス — 実装・レビュー・設計判断の前に参照すること

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
