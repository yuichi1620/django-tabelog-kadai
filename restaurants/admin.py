import csv
from io import TextIOWrapper

from django import forms
from django.contrib import admin, messages
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import path

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


class RestaurantCsvImportForm(forms.Form):
    csv_file = forms.FileField(label="CSVファイル")


def _parse_int(value, default=0):
    try:
        return int(str(value).strip() or default)
    except (TypeError, ValueError):
        return default


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    search_fields = ["name"]


@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "phone_number", "business_hours", "budget_min", "budget_max", "image", "created_at"]
    list_filter = ["category"]
    search_fields = ["name", "address", "phone_number", "business_hours"]
    actions = ["export_csv"]

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path("import-csv/", self.admin_site.admin_view(self.import_csv_view), name="restaurants_restaurant_import_csv"),
        ]
        return custom_urls + urls

    @admin.action(description="選択した店舗をCSV出力")
    def export_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
        response["Content-Disposition"] = 'attachment; filename="restaurants_export.csv"'
        writer = csv.writer(response)
        writer.writerow(
            [
                "id",
                "name",
                "category",
                "address",
                "phone_number",
                "business_hours",
                "description",
                "budget_min",
                "budget_max",
            ]
        )
        for r in queryset.select_related("category"):
            writer.writerow(
                [
                    r.id,
                    r.name,
                    r.category.name,
                    r.address,
                    r.phone_number,
                    r.business_hours,
                    r.description,
                    r.budget_min,
                    r.budget_max,
                ]
            )
        return response

    def import_csv_view(self, request):
        if request.method == "POST":
            form = RestaurantCsvImportForm(request.POST, request.FILES)
            if form.is_valid():
                file_obj = TextIOWrapper(form.cleaned_data["csv_file"].file, encoding="utf-8-sig")
                reader = csv.DictReader(file_obj)
                created_count = 0
                updated_count = 0
                for row in reader:
                    category_name = (row.get("category") or "").strip() or "未分類"
                    category, _ = Category.objects.get_or_create(name=category_name)
                    defaults = {
                        "phone_number": (row.get("phone_number") or "").strip(),
                        "business_hours": (row.get("business_hours") or "").strip(),
                        "description": (row.get("description") or "").strip(),
                        "budget_min": _parse_int(row.get("budget_min"), default=0),
                        "budget_max": _parse_int(row.get("budget_max"), default=0),
                        "category": category,
                    }
                    _, created = Restaurant.objects.update_or_create(
                        name=(row.get("name") or "").strip(),
                        address=(row.get("address") or "").strip(),
                        defaults=defaults,
                    )
                    if created:
                        created_count += 1
                    else:
                        updated_count += 1
                self.message_user(
                    request,
                    f"CSV取込が完了しました。新規: {created_count}件 / 更新: {updated_count}件",
                    level=messages.SUCCESS,
                )
                return redirect("..")
        else:
            form = RestaurantCsvImportForm()
        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "form": form,
            "title": "店舗CSV取込",
        }
        return render(request, "admin/restaurants/restaurant/import_csv.html", context)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["restaurant", "user", "rating", "is_public", "created_at"]
    list_filter = ["rating", "is_public", "created_at"]
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


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ["user", "full_name", "plan_status", "phone_number", "postal_code", "created_at", "updated_at"]
    list_filter = ["plan_status"]
    search_fields = ["user__username", "user__email", "full_name", "phone_number", "postal_code", "address"]
    actions = ["export_csv"]

    @admin.action(description="選択した会員をCSV出力")
    def export_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
        response["Content-Disposition"] = 'attachment; filename="members_export.csv"'
        writer = csv.writer(response)
        writer.writerow(
            [
                "id",
                "email",
                "full_name",
                "plan_status",
                "phone_number",
                "postal_code",
                "address",
                "created_at",
            ]
        )
        for m in queryset.select_related("user"):
            writer.writerow(
                [
                    m.id,
                    m.user.email,
                    m.full_name,
                    m.plan_status,
                    m.phone_number,
                    m.postal_code,
                    m.address,
                    m.created_at,
                ]
            )
        return response


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
