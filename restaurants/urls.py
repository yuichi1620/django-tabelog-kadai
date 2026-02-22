from django.urls import include, path

from . import views

app_name = "restaurants"

urlpatterns = [
    # Public
    path("", include("restaurants.urls_public")),
    # Account
    path("accounts/", include("restaurants.urls_account")),
    # Member
    path("members/", include("restaurants.urls_member")),
    path("mypage/", views.mypage, name="mypage"),
    # Membership
    path("membership/", include("restaurants.urls_membership")),
    # Webhook
    path("webhooks/", include("restaurants.urls_webhook")),
    # Management
    path("management/", include("restaurants.urls_management")),
    # 旧URL互換
    path("admin-dashboard/", views.admin_dashboard),
]
