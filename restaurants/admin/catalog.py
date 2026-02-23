import csv

from django.contrib import admin
from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import path
from django.utils.html import format_html

from restaurants.admin.common import RestaurantCsvImportForm, build_csv_response, parse_int, read_uploaded_csv
from restaurants.models import Category, Restaurant


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    search_fields = ["name"]


@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "category",
        "phone_number",
        "business_hours",
        "budget_min",
        "budget_max",
        "image_link",
        "created_at",
    ]
    list_filter = ["category"]
    search_fields = ["name", "address", "phone_number", "business_hours"]
    actions = ["export_csv"]

    @admin.display(description="店舗画像")
    def image_link(self, obj):
        if not obj.image:
            return "-"
        return format_html('<a href="{}" target="_blank" rel="noopener">画像を開く</a>', obj.image_display_url)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path("import-csv/", self.admin_site.admin_view(self.import_csv_view), name="restaurants_restaurant_import_csv"),
        ]
        return custom_urls + urls

    @admin.action(description="選択した店舗をCSV出力")
    def export_csv(self, request, queryset):
        response = build_csv_response("restaurants_export.csv")
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
                reader = read_uploaded_csv(form.cleaned_data["csv_file"])
                created_count = 0
                updated_count = 0
                for row in reader:
                    category_name = (row.get("category") or "").strip() or "未分類"
                    category, _ = Category.objects.get_or_create(name=category_name)
                    defaults = {
                        "phone_number": (row.get("phone_number") or "").strip(),
                        "business_hours": (row.get("business_hours") or "").strip(),
                        "description": (row.get("description") or "").strip(),
                        "budget_min": parse_int(row.get("budget_min"), default=0),
                        "budget_max": parse_int(row.get("budget_max"), default=0),
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
