from django.contrib import admin
from .models import (
    Category,
    Coupon,
    Favorite,
    Member,
    PaymentMethod,
    Reservation,
    Restaurant,
    Review,
    SiteSetting,
    StripeWebhookEvent,
    UserCoupon,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    search_fields = ["name"]


@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "phone_number", "business_hours", "budget_min", "budget_max", "image", "created_at"]
    list_filter = ["category"]
    search_fields = ["name", "address", "phone_number", "business_hours"]


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["restaurant", "user", "rating", "created_at"]
    list_filter = ["rating", "created_at"]
    search_fields = ["restaurant__name", "user__username"]


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ["user", "restaurant"]
    search_fields = ["user__username", "restaurant__name"]


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ["user", "full_name", "plan_status", "phone_number", "postal_code", "created_at", "updated_at"]
    list_filter = ["plan_status"]
    search_fields = ["user__username", "user__email", "full_name", "phone_number", "postal_code", "address"]


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ["restaurant", "user", "reserved_at", "people_count", "status", "created_at"]
    list_filter = ["status", "reserved_at"]
    search_fields = ["restaurant__name", "user__username", "user__email"]


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ["title", "restaurant", "discount_text", "is_active", "created_at"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["title", "restaurant__name"]


@admin.register(UserCoupon)
class UserCouponAdmin(admin.ModelAdmin):
    list_display = ["user", "coupon", "used_at", "created_at"]
    list_filter = ["used_at", "created_at"]
    search_fields = ["user__username", "user__email", "coupon__title"]


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ["member", "card_brand", "card_last4", "is_active", "updated_at"]
    list_filter = ["is_active", "updated_at"]
    search_fields = ["member__user__username", "member__user__email", "card_last4"]


@admin.register(SiteSetting)
class SiteSettingAdmin(admin.ModelAdmin):
    list_display = ["company_name", "updated_at"]


@admin.register(StripeWebhookEvent)
class StripeWebhookEventAdmin(admin.ModelAdmin):
    list_display = ["event_id", "event_type", "status", "received_at", "processed_at"]
    list_filter = ["status", "event_type", "received_at"]
    search_fields = ["event_id", "event_type", "last_error"]
