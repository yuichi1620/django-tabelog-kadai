from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid


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


class Category(models.Model):
    name = models.CharField("カテゴリ名", max_length=50, unique=True)

    class Meta:
        verbose_name = "カテゴリ"
        verbose_name_plural = "カテゴリ"

    def __str__(self):
        return self.name


class Restaurant(models.Model):
    name = models.CharField("店舗名", max_length=100)
    address = models.CharField("住所", max_length=200)
    phone_number = models.CharField("電話番号", max_length=20, blank=True)
    business_hours = models.CharField("営業時間", max_length=120, blank=True)
    description = models.TextField("説明", blank=True)
    image = models.FileField("店舗画像", upload_to="restaurants/", blank=True)

    budget_min = models.PositiveIntegerField("予算下限", default=0)
    budget_max = models.PositiveIntegerField("予算上限", default=0)

    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="restaurants"
    )

    created_at = models.DateTimeField("登録日", auto_now_add=True)

    class Meta:
        verbose_name = "店舗"
        verbose_name_plural = "店舗"

    def __str__(self):
        return self.name


class Reservation(models.Model):
    STATUS_ACTIVE = "active"
    STATUS_CANCELED = "canceled"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "予約中"),
        (STATUS_CANCELED, "キャンセル"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reservations",
    )
    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name="reservations",
    )
    reserved_at = models.DateTimeField("予約日時")
    people_count = models.PositiveSmallIntegerField("人数", default=1)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    created_at = models.DateTimeField("作成日", auto_now_add=True)

    class Meta:
        verbose_name = "予約"
        verbose_name_plural = "予約"
        ordering = ["-reserved_at"]

    def __str__(self):
        return f"{self.user} - {self.restaurant} ({self.reserved_at})"


class Review(models.Model):
    restaurant = models.ForeignKey(
        Restaurant, on_delete=models.CASCADE, related_name="reviews"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reviews",
    )

    rating = models.PositiveSmallIntegerField("評価(1-5)")
    comment = models.TextField("レビュー本文", blank=True)
    created_at = models.DateTimeField("投稿日", auto_now_add=True)

    class Meta:
        verbose_name = "レビュー"
        verbose_name_plural = "レビュー"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "restaurant"],
                name="unique_review_per_user_restaurant",
            )
        ]

    def __str__(self):
        return f"{self.restaurant.name} ({self.rating})"


class Favorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "restaurant"],
                name="unique_favorite_per_user_restaurant",
            )
        ]

    def __str__(self):
        return f"{self.user} - {self.restaurant.name}"


class Coupon(models.Model):
    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name="coupons",
    )
    title = models.CharField("クーポン名", max_length=100)
    description = models.TextField("説明", blank=True)
    discount_text = models.CharField("割引内容", max_length=100, blank=True)
    is_active = models.BooleanField("有効", default=True)
    created_at = models.DateTimeField("作成日", auto_now_add=True)

    class Meta:
        verbose_name = "クーポン"
        verbose_name_plural = "クーポン"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class UserCoupon(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="user_coupons")
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name="user_coupons")
    used_at = models.DateTimeField("使用日時", blank=True, null=True)
    created_at = models.DateTimeField("取得日時", auto_now_add=True)

    class Meta:
        verbose_name = "会員クーポン"
        verbose_name_plural = "会員クーポン"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "coupon"],
                name="unique_user_coupon",
            )
        ]

    def __str__(self):
        return f"{self.user} - {self.coupon}"


class PaymentMethod(models.Model):
    member = models.OneToOneField(Member, on_delete=models.CASCADE, related_name="payment_method")
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


class SiteSetting(models.Model):
    company_name = models.CharField("会社名", max_length=100, default="NAGOYAMESHI")
    company_description = models.TextField("会社概要", blank=True)
    terms_of_service = models.TextField("利用規約", blank=True)
    updated_at = models.DateTimeField("更新日", auto_now=True)

    class Meta:
        verbose_name = "基本情報設定"
        verbose_name_plural = "基本情報設定"

    def __str__(self):
        return self.company_name


class StripeWebhookEvent(models.Model):
    STATUS_PENDING = "pending"
    STATUS_PROCESSED = "processed"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "未処理"),
        (STATUS_PROCESSED, "処理済み"),
        (STATUS_FAILED, "失敗"),
    ]

    event_id = models.CharField("StripeイベントID", max_length=255, unique=True)
    event_type = models.CharField("イベント種別", max_length=100)
    status = models.CharField("処理状態", max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    last_error = models.TextField("最終エラー", blank=True)
    received_at = models.DateTimeField("受信日時", auto_now_add=True)
    processed_at = models.DateTimeField("処理日時", blank=True, null=True)

    class Meta:
        verbose_name = "StripeWebhookイベント"
        verbose_name_plural = "StripeWebhookイベント"
        ordering = ["-received_at"]

    def __str__(self):
        return f"{self.event_type} ({self.event_id})"
