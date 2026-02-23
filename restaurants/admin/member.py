import csv

from django.contrib import admin

from restaurants.admin.common import build_csv_response
from restaurants.models import Member, PaymentMethod


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ["user", "full_name", "plan_status", "phone_number", "postal_code", "created_at", "updated_at"]
    list_filter = ["plan_status"]
    search_fields = ["user__username", "user__email", "full_name", "phone_number", "postal_code", "address"]
    actions = ["export_csv"]

    @admin.action(description="選択した会員をCSV出力")
    def export_csv(self, request, queryset):
        response = build_csv_response("members_export.csv")
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


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ["member", "card_brand", "card_last4", "is_active", "updated_at"]
    list_filter = ["is_active", "updated_at"]
    search_fields = ["member__user__username", "member__user__email", "card_last4"]

