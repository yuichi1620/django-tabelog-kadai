from django.urls import path

from . import views


urlpatterns = [
    path("dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("members/", views.admin_member_list, name="admin_member_list"),
    path("members/<int:pk>/", views.admin_member_detail, name="admin_member_detail"),
    path("restaurants/", views.admin_restaurant_list, name="admin_restaurant_list"),
    path("restaurants/<int:pk>/", views.admin_restaurant_detail, name="admin_restaurant_detail"),
    path("reviews/<int:pk>/delete/", views.admin_review_delete, name="admin_review_delete"),
    path("reviews/", views.admin_review_list, name="admin_review_list"),
    path("reviews/<int:pk>/visibility/", views.admin_review_visibility_toggle, name="admin_review_visibility_toggle"),
    path("categories/", views.admin_category_list, name="admin_category_list"),
    path("sales/", views.admin_sales_list, name="admin_sales_list"),
]
