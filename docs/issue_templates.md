# NAGOYAMESHI 実装チケット（Issueテンプレート）

## 使い方
- 各チケットを 1 Issue として起票してください。
- `Depends on` を先に完了してから着手してください。
- 見積は 1 人開発の目安です。

## T01 会員登録を氏名/メール/パスワードに変更
- Priority: High
- Estimate: 1.5d
- Depends on: なし
- Scope:
  - `SignUpForm` を `name`, `email`, `password` ベースへ変更
  - メール重複チェック
  - ログインIDをメールへ統一（設定含む）
- Acceptance Criteria:
  - 氏名/メール/パスワードで会員登録できる
  - 同一メールの重複登録を防止できる
  - メール+パスワードでログインできる

## T02 メール認証フロー実装
- Priority: High
- Estimate: 1.5d
- Depends on: T01
- Scope:
  - 仮登録トークン発行
  - 認証メール送信
  - 認証完了後に本登録化
- Acceptance Criteria:
  - 登録時に認証メールが送信される
  - 認証リンクから有効化できる
  - 未認証ユーザーは制限される

## T03 会員区分（無料/有料）をモデル追加
- Priority: High
- Estimate: 1.0d
- Depends on: T01
- Scope:
  - `Member` に `plan_status`（free/paid）追加
  - `paid_until` など契約状態管理カラム追加
- Acceptance Criteria:
  - 会員ごとに無料/有料を保持できる
  - 管理画面で状態確認できる

## T04 有料会員制御デコレータ実装
- Priority: High
- Estimate: 0.5d
- Depends on: T03
- Scope:
  - `@paid_member_required` 作成
  - 非有料アクセス時のアップグレード導線
- Acceptance Criteria:
  - 対象画面で無料会員をブロックできる
  - 適切な遷移先/メッセージが表示される

## T05 お気に入り/レビューを有料会員限定化
- Priority: High
- Estimate: 0.5d
- Depends on: T04
- Scope:
  - `toggle_favorite`, `favorite_list`, `review_create`, `review_delete` に有料制御適用
- Acceptance Criteria:
  - 無料会員では実行できない
  - 有料会員は既存通り実行できる

## T06 Stripe サブスク契約導入
- Priority: High
- Estimate: 2.0d
- Depends on: T03
- Scope:
  - Checkout セッション生成
  - 成功/失敗ハンドリング
  - 契約状態を `Member` に反映
- Acceptance Criteria:
  - サブスク開始できる
  - 成功時に `paid` へ遷移する
  - エラー時に安全に復帰できる

## T07 Stripe Webhook 受信実装
- Priority: High
- Estimate: 1.0d
- Depends on: T06
- Scope:
  - `invoice.paid`, `customer.subscription.deleted` 等を処理
  - 冪等性と署名検証
- Acceptance Criteria:
  - Webhook イベントで会員状態が同期される
  - 同一イベント重複受信で破綻しない

## T08 予約モデル/予約作成機能
- Priority: High
- Estimate: 1.5d
- Depends on: T04
- Scope:
  - `Reservation` モデル追加（日時/人数/状態）
  - 店舗詳細から予約作成
  - 予約確定確認（モーダル相当）
- Acceptance Criteria:
  - 有料会員のみ予約作成できる
  - 予約データが永続化される

## T09 予約一覧/キャンセル機能
- Priority: High
- Estimate: 1.0d
- Depends on: T08
- Scope:
  - マイページ予約一覧
  - 予約日時前のみキャンセル可
- Acceptance Criteria:
  - 自分の予約だけ一覧表示される
  - 過去予約はキャンセル不可

## T10 予約完了メール送信
- Priority: Medium
- Estimate: 0.5d
- Depends on: T08
- Scope:
  - 予約確定時メール通知
  - 失敗時のログ出力
- Acceptance Criteria:
  - 予約完了時にメールが送信される
  - 送信失敗時も予約処理は整合を保つ

## T11 マイページ統合（会員情報/予約/お気に入り）
- Priority: Medium
- Estimate: 1.0d
- Depends on: T09, T05
- Scope:
  - マイページ作成
  - 会員情報、予約一覧、お気に入り一覧を集約
- Acceptance Criteria:
  - 1 画面で主要情報へアクセスできる
  - 既存画面への導線が統一される

## T12 退会機能
- Priority: Medium
- Estimate: 0.5d
- Depends on: T11
- Scope:
  - 退会確認
  - ユーザー/関連データの無効化または削除
- Acceptance Criteria:
  - 退会後ログイン不可
  - データ整合性が保たれる

## T13 人気順ソート追加
- Priority: Medium
- Estimate: 0.5d
- Depends on: なし
- Scope:
  - 店舗一覧に `popular` ソート追加（レビュー件数 or お気に入り数）
- Acceptance Criteria:
  - 人気順で並び替えできる
  - ページネーション時にソート条件が維持される

## T14 クーポン機能（有料限定）
- Priority: Low
- Estimate: 1.5d
- Depends on: T04
- Scope:
  - クーポン表示/取得/使用状態管理
- Acceptance Criteria:
  - 有料会員のみ利用できる
  - 使用済み管理ができる

## T15 管理者: 集計ダッシュボード
- Priority: High
- Estimate: 1.5d
- Depends on: T03, T08, T06
- Scope:
  - 総会員数、無料/有料、総予約数、店舗数、月間売上を表示
- Acceptance Criteria:
  - 管理画面トップで各KPIが確認できる
  - 値がDBと一致する

## T16 管理者: 会員管理強化
- Priority: Medium
- Estimate: 1.0d
- Depends on: T03
- Scope:
  - 会員検索（氏名/メール）
  - 無料/有料フィルタ
  - 会員詳細表示
- Acceptance Criteria:
  - 条件検索できる
  - 会員区分で絞り込める

## T17 管理者: 基本情報設定（会社概要/利用規約）
- Priority: Low
- Estimate: 1.0d
- Depends on: なし
- Scope:
  - CMS的な設定モデルを作り、管理画面から編集
- Acceptance Criteria:
  - 会社概要と利用規約を管理画面で変更できる
  - フロント表示に反映される

## T18 テスト拡充（認証/課金/予約）
- Priority: High
- Estimate: 1.5d
- Depends on: T01-T17
- Scope:
  - モデル/ビュー/権限制御/Webhook の回帰テスト
- Acceptance Criteria:
  - 主要ユースケースが自動テスト化される
  - CI で安定実行できる
