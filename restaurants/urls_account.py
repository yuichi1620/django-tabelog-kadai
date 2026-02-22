from django.urls import path

from . import views


urlpatterns = [
    path("signup/", views.signup, name="signup"),
    path("resend-verification/", views.resend_verification_email, name="resend_verification_email"),
    path("verify/<uidb64>/<token>/", views.verify_email, name="verify_email"),
    path("email-change/verify/<str:token>/", views.verify_email_change, name="verify_email_change"),
]
