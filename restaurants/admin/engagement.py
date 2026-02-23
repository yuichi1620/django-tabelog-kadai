from django.contrib import admin, messages

from restaurants.models import Coupon, Favorite, Reservation, Review, UserCoupon


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = [
        "restaurant",
        "user",
        "rating",
        "rating_atmosphere",
        "rating_taste",
        "rating_price",
        "rating_service",
        "is_public",
        "created_at",
    ]
    list_filter = ["rating", "rating_atmosphere", "rating_taste", "rating_price", "rating_service", "is_public", "created_at"]
    search_fields = ["restaurant__name", "user__username", "user__email"]
    actions = ["make_public", "make_non_public"]

    @admin.action(description="選択レビューを公開にする")
    def make_public(self, request, queryset):
        updated = queryset.update(is_public=True)
        self.message_user(request, f"{updated}件のレビューを公開にしました。", level=messages.SUCCESS)

    @admin.action(description="選択レビューを非公開にする")
    def make_non_public(self, request, queryset):
        updated = queryset.update(is_public=False)
        self.message_user(request, f"{updated}件のレビューを非公開にしました。", level=messages.SUCCESS)


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ["user", "restaurant"]
    search_fields = ["user__username", "restaurant__name"]


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

