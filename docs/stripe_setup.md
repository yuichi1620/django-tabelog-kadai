# Stripe ローカルセットアップ手順

## 1. 環境変数を作成
1. `cp .env.example .env`
2. `.env` に以下を設定
   - `STRIPE_SECRET_KEY`
   - `STRIPE_PRICE_ID`
   - `APP_BASE_URL`（通常 `http://127.0.0.1:8000`）

## 2. Webhook シークレットを取得
1. `scripts/stripe_print_secret.sh` を実行
2. 出力された `whsec_...` を `.env` の `STRIPE_WEBHOOK_SECRET` に設定

## 3. Django を起動
- `scripts/runserver_with_env.sh`

## 4. Webhook 転送を起動（別ターミナル）
- `scripts/stripe_listen.sh`

## 5. 動作確認
1. ログイン後、`/membership/upgrade/` へアクセス
2. 「Stripeで有料会員登録する」を押す
3. 決済完了後、Webhook 到達で会員ステータスが `paid` に更新される

## 補足
- Stripe テストカード例: `4242 4242 4242 4242`
- Webhook URL: `http://127.0.0.1:8000/webhooks/stripe/`
- メール変更認証リンク期限: `.env` の `EMAIL_CHANGE_TOKEN_MAX_AGE`（秒）
- DBバックアップ: `scripts/backup_db.sh`
