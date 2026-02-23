from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


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
        "Restaurant",
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
    SCORE_VALIDATORS = [MinValueValidator(1), MaxValueValidator(5)]

    restaurant = models.ForeignKey(
        "Restaurant",
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reviews",
    )

    rating = models.PositiveSmallIntegerField("総合評価(1-5)", validators=SCORE_VALIDATORS)
    rating_atmosphere = models.PositiveSmallIntegerField("雰囲気(1-5)", validators=SCORE_VALIDATORS, default=3)
    rating_taste = models.PositiveSmallIntegerField("味(1-5)", validators=SCORE_VALIDATORS, default=3)
    rating_price = models.PositiveSmallIntegerField("値段(1-5)", validators=SCORE_VALIDATORS, default=3)
    rating_service = models.PositiveSmallIntegerField("接客(1-5)", validators=SCORE_VALIDATORS, default=3)
    comment = models.TextField("レビュー本文", blank=True)
    is_public = models.BooleanField("公開状態", default=True)
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

    def calculate_overall_rating(self):
        total = self.rating_atmosphere + self.rating_taste + self.rating_price + self.rating_service
        return (total + 2) // 4

    def save(self, *args, **kwargs):
        self.rating = self.calculate_overall_rating()
        super().save(*args, **kwargs)


class Favorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    restaurant = models.ForeignKey("Restaurant", on_delete=models.CASCADE)

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
        "Restaurant",
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
    coupon = models.ForeignKey("Coupon", on_delete=models.CASCADE, related_name="user_coupons")
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

