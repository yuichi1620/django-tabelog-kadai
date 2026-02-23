import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Member(models.Model):
    PLAN_FREE = "free"
    PLAN_PAID = "paid"
    PLAN_CHOICES = [
        (PLAN_FREE, "無料会員"),
        (PLAN_PAID, "有料会員"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="member_profile",
    )
    full_name = models.CharField("氏名", max_length=100, blank=True)
    phone_number = models.CharField("電話番号", max_length=20, blank=True)
    postal_code = models.CharField("郵便番号", max_length=20, blank=True)
    address = models.CharField("住所", max_length=255, blank=True)
    plan_status = models.CharField(
        "会員プラン",
        max_length=10,
        choices=PLAN_CHOICES,
        default=PLAN_FREE,
    )
    paid_started_at = models.DateTimeField("有料会員開始日", blank=True, null=True)
    paid_ended_at = models.DateTimeField("有料会員終了日", blank=True, null=True)
    stripe_customer_id = models.CharField("Stripe顧客ID", max_length=100, blank=True)
    stripe_subscription_id = models.CharField("StripeサブスクID", max_length=100, blank=True)
    stripe_subscription_status = models.CharField("Stripeサブスク状態", max_length=40, blank=True)
    pending_email = models.EmailField("変更申請中メールアドレス", blank=True)
    email_change_requested_at = models.DateTimeField("メール変更申請日時", blank=True, null=True)
    email_change_token = models.UUIDField("メール変更トークン", blank=True, null=True, default=None)
    created_at = models.DateTimeField("登録日", auto_now_add=True)
    updated_at = models.DateTimeField("更新日", auto_now=True)

    class Meta:
        verbose_name = "会員情報"
        verbose_name_plural = "会員情報"

    def __str__(self):
        return f"Member({self.user})"

    @property
    def is_paid(self):
        if self.plan_status != self.PLAN_PAID:
            return False
        if self.paid_ended_at and self.paid_ended_at < timezone.now():
            return False
        return True

    def issue_email_change_token(self):
        self.email_change_token = uuid.uuid4()
        self.email_change_requested_at = timezone.now()


class PaymentMethod(models.Model):
    member = models.OneToOneField("Member", on_delete=models.CASCADE, related_name="payment_method")
    card_brand = models.CharField("カードブランド", max_length=20, blank=True)
    card_last4 = models.CharField("下4桁", max_length=4, blank=True)
    token = models.CharField("トークン", max_length=255, blank=True)
    is_active = models.BooleanField("有効", default=True)
    updated_at = models.DateTimeField("更新日", auto_now=True)

    class Meta:
        verbose_name = "カード情報"
        verbose_name_plural = "カード情報"

    def __str__(self):
        return f"{self.member.user} - {self.card_brand} {self.card_last4}"

