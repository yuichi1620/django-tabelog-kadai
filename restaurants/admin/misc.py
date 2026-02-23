from django.contrib import admin

from restaurants.models import SiteSetting, StripeWebhookEvent


@admin.register(SiteSetting)
class SiteSettingAdmin(admin.ModelAdmin):
    list_display = ["company_name", "updated_at"]


@admin.register(StripeWebhookEvent)
class StripeWebhookEventAdmin(admin.ModelAdmin):
    list_display = ["event_id", "event_type", "status", "received_at", "processed_at"]
    list_filter = ["status", "event_type", "received_at"]

