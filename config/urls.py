"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
from django.views.generic.base import RedirectView
from restaurants import views as restaurant_views

urlpatterns = [
    # 旧カスタム管理URL互換（/admin 配下の独自ページを /management 配下へ誘導）
    path("admin/members/", RedirectView.as_view(pattern_name="restaurants:admin_member_list", permanent=False)),
    path("admin/members/<int:pk>/", RedirectView.as_view(pattern_name="restaurants:admin_member_detail", permanent=False)),
    path("admin/restaurants/", RedirectView.as_view(pattern_name="restaurants:admin_restaurant_list", permanent=False)),
    path("admin/restaurants/<int:pk>/", RedirectView.as_view(pattern_name="restaurants:admin_restaurant_detail", permanent=False)),
    path("admin/reviews/", RedirectView.as_view(pattern_name="restaurants:admin_review_list", permanent=False)),
    path("admin/reviews/<int:pk>/delete/", restaurant_views.admin_review_delete),
    path("admin/reviews/<int:pk>/visibility/", restaurant_views.admin_review_visibility_toggle),
    path("admin/categories/", RedirectView.as_view(pattern_name="restaurants:admin_category_list", permanent=False)),
    path("admin/sales/", RedirectView.as_view(pattern_name="restaurants:admin_sales_list", permanent=False)),
    path('admin/', admin.site.urls),
    path('', include('restaurants.urls')),
    path('accounts/', include('django.contrib.auth.urls')),
]

if not settings.DEBUG:
    urlpatterns.insert(
        0,
        path("media/restaurants/<path:path>", restaurant_views.legacy_media_restaurant_image),
    )

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
