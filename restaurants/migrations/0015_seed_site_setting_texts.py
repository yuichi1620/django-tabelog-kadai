from django.db import migrations


COMPANY_DESCRIPTION_TEXT = """NAGOYAMESHI（ナゴヤメシ）は、名古屋エリアの飲食店情報を分かりやすく届けることを目的としたグルメ情報サービスです。

ユーザーが店舗の特徴、予算、レビューを比較しながら、自分に合ったお店を見つけられる体験を大切にしています。
また、レビューや予約、クーポン機能を通じて、飲食店とユーザー双方にとって使いやすい地域密着型プラットフォームを目指しています。

運営者情報
サービス名: NAGOYAMESHI
連絡先: support@nagoyameshi.example
営業時間: 平日 10:00〜18:00（土日祝を除く）"""


TERMS_OF_SERVICE_TEXT = """第1条（適用）
本規約は、NAGOYAMESHI（以下「当サービス」）の利用条件を定めるものです。ユーザーは、本規約に同意のうえ当サービスを利用するものとします。

第2条（会員登録）
ユーザーは、当サービス所定の方法により会員登録を行うことができます。登録情報は正確かつ最新の内容を保持してください。

第3条（アカウント管理）
ユーザーは自己の責任においてアカウント情報を管理するものとし、第三者への貸与・譲渡はできません。

第4条（投稿情報）
ユーザーが投稿したレビュー等の内容について、ユーザーは自ら責任を負うものとします。
当サービスは、法令違反または不適切と判断した投稿を事前通知なく非公開または削除できるものとします。

第5条（禁止事項）
ユーザーは、以下の行為をしてはなりません。
・法令または公序良俗に違反する行為
・虚偽情報の登録、なりすまし行為
・サービス運営を妨げる行為
・第三者の権利または利益を侵害する行為

第6条（有料機能）
有料会員機能の料金、提供内容、支払方法は当サービス上の表示に従います。
決済・請求情報管理には外部決済サービスを利用する場合があります。

第7条（サービスの変更・停止）
当サービスは、保守や障害対応等のため、事前通知なくサービス内容の変更または提供停止を行う場合があります。

第8条（免責）
当サービスは、掲載情報の完全性・正確性・有用性について保証するものではありません。
ユーザーに生じた損害について、当サービスに故意または重過失がある場合を除き、責任を負いません。

第9条（規約変更）
当サービスは、必要と判断した場合に本規約を変更できるものとします。変更後の規約は、当サービス上に表示した時点で効力を生じます。

第10条（準拠法・管轄）
本規約は日本法に準拠し、本サービスに関連して生じる紛争は、運営者所在地を管轄する裁判所を第一審の専属的合意管轄とします。

制定日: 2026年2月22日"""


def seed_site_setting_texts(apps, schema_editor):
    SiteSetting = apps.get_model("restaurants", "SiteSetting")
    setting = SiteSetting.objects.first()
    if setting is None:
        SiteSetting.objects.create(
            company_name="NAGOYAMESHI",
            company_description=COMPANY_DESCRIPTION_TEXT,
            terms_of_service=TERMS_OF_SERVICE_TEXT,
        )
        return

    update_fields = []
    if not setting.company_name:
        setting.company_name = "NAGOYAMESHI"
        update_fields.append("company_name")
    if not (setting.company_description or "").strip():
        setting.company_description = COMPANY_DESCRIPTION_TEXT
        update_fields.append("company_description")
    if not (setting.terms_of_service or "").strip():
        setting.terms_of_service = TERMS_OF_SERVICE_TEXT
        update_fields.append("terms_of_service")

    if update_fields:
        setting.save(update_fields=update_fields)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("restaurants", "0014_review_detailed_scores"),
    ]

    operations = [
        migrations.RunPython(seed_site_setting_texts, noop_reverse),
    ]
