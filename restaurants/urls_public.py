from django.urls import path

from . import views


urlpatterns = [
    path("", views.restaurant_list, name="list"),
    path("terms/", views.terms, name="terms"),
    path("restaurants/<int:pk>/", views.restaurant_detail, name="detail"),
    path("restaurants/<int:pk>/favorite/", views.toggle_favorite, name="toggle_favorite"),
    path("favorites/", views.favorite_list, name="favorite_list"),
    path("restaurants/<int:pk>/reviews/", views.review_create, name="review_create"),
    path("restaurants/<int:pk>/reviews/delete/", views.review_delete, name="review_delete"),
    path("coupons/<int:pk>/use/", views.coupon_use, name="coupon_use"),
    path("restaurants/<int:pk>/reservations/", views.reservation_create, name="reservation_create"),
    path("reservations/", views.reservation_list, name="reservation_list"),
    path("reservations/<int:pk>/cancel/", views.reservation_cancel, name="reservation_cancel"),
]
