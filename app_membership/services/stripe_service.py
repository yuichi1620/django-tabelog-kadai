from django.conf import settings
from django.urls import reverse
from django.utils import timezone
import stripe

from restaurants.models import Member

stripe.api_key = settings.STRIPE_SECRET_KEY


def ensure_stripe_customer(member, user):
    if member.stripe_customer_id:
        return member.stripe_customer_id
    customer = stripe.Customer.create(
        email=user.email,
        name=member.full_name or user.first_name or user.email,
        metadata={"user_id": str(user.id)},
    )
    member.stripe_customer_id = customer.id
    member.save(update_fields=["stripe_customer_id"])
    return member.stripe_customer_id


def create_checkout_session_url(*, member, user):
    customer_id = ensure_stripe_customer(member, user)
    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        line_items=[{"price": settings.STRIPE_PRICE_ID, "quantity": 1}],
        success_url=f"{settings.APP_BASE_URL}{reverse('restaurants:billing_success')}?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{settings.APP_BASE_URL}{reverse('restaurants:upgrade_membership')}",
        metadata={"user_id": str(user.id)},
    )
    return session.url


def process_billing_success(*, user, session_id):
    session = stripe.checkout.Session.retrieve(session_id)
    if not session or session.get("payment_status") not in ("paid", "no_payment_required"):
        return {"status": "ignored"}

    metadata = session.get("metadata") or {}
    session_user_id = str(metadata.get("user_id") or "")
    session_customer_id = session.get("customer")

    if session_user_id and session_user_id != str(user.id):
        return {"status": "foreign_user"}

    member, _ = Member.objects.get_or_create(
        user=user,
        defaults={"full_name": user.first_name},
    )
    if member.stripe_customer_id and session_customer_id and member.stripe_customer_id != session_customer_id:
        return {"status": "customer_mismatch"}

    member.stripe_customer_id = session.get("customer") or member.stripe_customer_id
    member.stripe_subscription_id = session.get("subscription") or member.stripe_subscription_id
    member.plan_status = Member.PLAN_PAID
    member.paid_started_at = timezone.now()
    member.paid_ended_at = None
    member.stripe_subscription_status = "active"
    member.save(
        update_fields=[
            "stripe_customer_id",
            "stripe_subscription_id",
            "plan_status",
            "paid_started_at",
            "paid_ended_at",
            "stripe_subscription_status",
        ]
    )
    return {"status": "updated"}


def create_billing_portal_session_url(*, member, user):
    customer_id = ensure_stripe_customer(member, user)
    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=f"{settings.APP_BASE_URL}{reverse('restaurants:mypage')}",
    )
    return session.url


def cancel_membership(member):
    if member.stripe_subscription_id:
        stripe.Subscription.modify(
            member.stripe_subscription_id,
            cancel_at_period_end=True,
        )
        return "scheduled"

    member.plan_status = Member.PLAN_FREE
    member.paid_ended_at = timezone.now()
    member.save(update_fields=["plan_status", "paid_ended_at"])
    return "canceled_locally"

