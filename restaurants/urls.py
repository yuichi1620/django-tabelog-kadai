from django.urls import path
from . import views

app_name = "restaurants"

urlpatterns = [
    path("", views.restaurant_list, name="list"),
    path("accounts/signup/", views.signup, name="signup"),
    path("accounts/verify/<uidb64>/<token>/", views.verify_email, name="verify_email"),
    path("accounts/email-change/verify/<str:token>/", views.verify_email_change, name="verify_email_change"),
    path("restaurants/<int:pk>/", views.restaurant_detail, name="detail"),

    # お気に入り
    path("restaurants/<int:pk>/favorite/", views.toggle_favorite, name="toggle_favorite"),
    path("favorites/", views.favorite_list, name="favorite_list"),

    # レビュー
    path("restaurants/<int:pk>/reviews/", views.review_create, name="review_create"),
    path("restaurants/<int:pk>/reviews/delete/", views.review_delete, name="review_delete"),
    path("coupons/<int:pk>/use/", views.coupon_use, name="coupon_use"),

    # 予約
    path("restaurants/<int:pk>/reservations/", views.reservation_create, name="reservation_create"),
    path("reservations/", views.reservation_list, name="reservation_list"),
    path("reservations/<int:pk>/cancel/", views.reservation_cancel, name="reservation_cancel"),

    # 会員情報
    path("members/profile/edit/", views.member_profile_edit, name="member_profile_edit"),
    path("members/account/edit/", views.member_account_edit, name="member_account_edit"),
    path("mypage/", views.mypage, name="mypage"),
    path("members/withdraw/", views.withdraw, name="withdraw"),

    # 有料会員
    path("membership/upgrade/", views.upgrade_membership, name="upgrade_membership"),
    path("membership/checkout/", views.create_checkout_session, name="create_checkout_session"),
    path("membership/billing/success/", views.billing_success, name="billing_success"),
    path("membership/portal/", views.create_billing_portal_session, name="create_billing_portal_session"),
    path("membership/cancel/", views.cancel_membership, name="cancel_membership"),
    path("membership/payment-method/", views.payment_method_edit, name="payment_method_edit"),
    path("membership/payment-method/delete/", views.payment_method_delete, name="payment_method_delete"),
    path("webhooks/stripe/", views.stripe_webhook, name="stripe_webhook"),

    # 基本情報
    path("terms/", views.terms, name="terms"),

    # 管理者
    path("admin-dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("admin/members/", views.admin_member_list, name="admin_member_list"),
    path("admin/members/<int:pk>/", views.admin_member_detail, name="admin_member_detail"),
    path("admin/restaurants/", views.admin_restaurant_list, name="admin_restaurant_list"),
    path("admin/restaurants/<int:pk>/", views.admin_restaurant_detail, name="admin_restaurant_detail"),
    path("admin/reviews/<int:pk>/delete/", views.admin_review_delete, name="admin_review_delete"),
    path("admin/categories/", views.admin_category_list, name="admin_category_list"),
]
