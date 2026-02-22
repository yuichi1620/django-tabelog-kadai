from django.urls import path

from . import views


urlpatterns = [
    path("upgrade/", views.upgrade_membership, name="upgrade_membership"),
    path("checkout/", views.create_checkout_session, name="create_checkout_session"),
    path("billing/success/", views.billing_success, name="billing_success"),
    path("portal/", views.create_billing_portal_session, name="create_billing_portal_session"),
    path("cancel/", views.cancel_membership, name="cancel_membership"),
    path("payment-method/", views.payment_method_edit, name="payment_method_edit"),
    path("payment-method/delete/", views.payment_method_delete, name="payment_method_delete"),
]
