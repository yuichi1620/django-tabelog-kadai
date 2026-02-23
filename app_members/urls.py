from django.urls import path

from app_members import views


urlpatterns = [
    path("members/profile/edit/", views.member_profile_edit, name="member_profile_edit"),
    path("members/account/edit/", views.member_account_edit, name="member_account_edit"),
    path("members/withdraw/", views.withdraw, name="withdraw"),
    path("mypage/", views.mypage, name="mypage"),
]

