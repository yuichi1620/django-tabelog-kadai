from django.urls import include, path

from app_management import views as management_views

app_name = "restaurants"

urlpatterns = [
    # Public
    path("", include("app_public.urls")),
    # Account
    path("accounts/", include("app_accounts.urls")),
    # Member
    path("", include("app_members.urls")),
    # Membership
    path("membership/", include("app_membership.urls")),
    # Webhook
    path("webhooks/", include("app_webhooks.urls")),
    # Management
    path("management/", include("app_management.urls")),
    # 旧URL互換
    path("admin-dashboard/", management_views.admin_dashboard),
]
