from django.urls import path

from app_webhooks import views


urlpatterns = [
    path("stripe/", views.stripe_webhook, name="stripe_webhook"),
]

