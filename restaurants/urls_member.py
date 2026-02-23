from django.urls import path

from app_members import views


urlpatterns = [
    path("profile/edit/", views.member_profile_edit, name="member_profile_edit"),
    path("account/edit/", views.member_account_edit, name="member_account_edit"),
    path("withdraw/", views.withdraw, name="withdraw"),
]
