# 提出前チェックリスト

最終更新: 2026-02-18

## 1. マイグレーション整合
- [x] `venv/bin/python manage.py showmigrations restaurants`
  - `0011_stripewebhookevent` まで適用済み
- [x] `venv/bin/python manage.py migrate`
  - 未適用なし（実行時点）

## 2. アプリ整合チェック
- [x] `venv/bin/python manage.py check`
  - `System check identified no issues`
- [x] `venv/bin/python manage.py test`
  - `Ran 15 tests ... OK`

## 3. 主要機能テスト（自動）
- [x] 店舗一覧ソート/検索（テスト内で確認）
- [x] 有料会員制限（レビュー/お気に入り）
- [x] 予約作成/キャンセル
- [x] 会員登録メール送信
- [x] メール変更再認証（再送で旧リンク無効化）
- [x] Stripe Webhook 冪等化
  - `venv/bin/python manage.py test restaurants.tests.StripeWebhookIdempotencyTests`

## 4. 運用系
- [x] ログ出力先
  - `logs/app.log` 作成確認
- [x] バックアップスクリプト
  - `./scripts/backup_db.sh` 実行確認
  - 出力先: `backups/db_YYYYMMDD_HHMMSS.sqlite3`

## 5. 環境変数
- [x] `.env` に必要キーが存在
  - `APP_BASE_URL`
  - `DEFAULT_FROM_EMAIL`
  - `STRIPE_SECRET_KEY`
  - `STRIPE_PRICE_ID`
  - `STRIPE_WEBHOOK_SECRET`

## 6. 提出直前の手動確認（ブラウザ）
- [ ] 一般会員で `/favorites/`, `/reservations/` がアップグレード誘導される
- [ ] 有料会員でレビュー投稿/予約/お気に入りが実行できる
- [ ] `/members/account/edit/` でメール変更時に再認証メールが送信される
- [ ] Stripe テスト決済で `/webhooks/stripe/` 到達後に `Member.plan_status=paid` になる
- [ ] 管理画面で会員・店舗・カテゴリ・レビュー管理画面が表示される

## 7. 提出コマンド（最終実行推奨）
```bash
venv/bin/python manage.py migrate
venv/bin/python manage.py check
venv/bin/python manage.py test
```
