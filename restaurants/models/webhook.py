from django.db import models


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

