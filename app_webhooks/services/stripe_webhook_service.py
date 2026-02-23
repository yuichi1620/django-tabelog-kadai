import json

from django.conf import settings
from django.db import transaction
from django.utils import timezone
import stripe

from restaurants.models import Member, StripeWebhookEvent

stripe.api_key = settings.STRIPE_SECRET_KEY


def parse_event(*, payload, signature):
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET
    if endpoint_secret:
        return stripe.Webhook.construct_event(payload, signature, endpoint_secret)

    if not settings.DEBUG:
        raise ValueError("Unsigned webhook payload is not allowed in production.")
    return json.loads(payload.decode("utf-8"))


def process_event(event):
    event_id = event.get("id")
    event_type = event.get("type", "")
    data = event.get("data", {}).get("object", {})
    if not event_id or not event_type:
        return 400

    with transaction.atomic():
        webhook_event, _ = StripeWebhookEvent.objects.select_for_update().get_or_create(
            event_id=event_id,
            defaults={
                "event_type": event_type,
                "status": StripeWebhookEvent.STATUS_PENDING,
            },
        )
        if webhook_event.status == StripeWebhookEvent.STATUS_PROCESSED:
            return 200
        webhook_event.event_type = event_type
        webhook_event.status = StripeWebhookEvent.STATUS_PENDING
        webhook_event.last_error = ""
        webhook_event.save(update_fields=["event_type", "status", "last_error"])

    try:
        if event_type == "checkout.session.completed":
            customer_id = data.get("customer")
            subscription_id = data.get("subscription")
            user_id = (data.get("metadata") or {}).get("user_id")
            member = None
            if user_id:
                member = Member.objects.filter(user_id=user_id).first()
            if not member and customer_id:
                member = Member.objects.filter(stripe_customer_id=customer_id).first()
            if member:
                member.stripe_customer_id = customer_id or member.stripe_customer_id
                member.stripe_subscription_id = subscription_id or member.stripe_subscription_id
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

        elif event_type in ("customer.subscription.updated", "customer.subscription.deleted"):
            customer_id = data.get("customer")
            subscription_id = data.get("id")
            status = data.get("status", "")
            member = Member.objects.filter(stripe_customer_id=customer_id).first()
            if member:
                member.stripe_subscription_id = subscription_id or member.stripe_subscription_id
                member.stripe_subscription_status = status
                if status in ("active", "trialing", "past_due"):
                    member.plan_status = Member.PLAN_PAID
                    if not member.paid_started_at:
                        member.paid_started_at = timezone.now()
                    member.paid_ended_at = None
                else:
                    member.plan_status = Member.PLAN_FREE
                    member.paid_ended_at = timezone.now()
                member.save(
                    update_fields=[
                        "stripe_subscription_id",
                        "stripe_subscription_status",
                        "plan_status",
                        "paid_started_at",
                        "paid_ended_at",
                    ]
                )
    except Exception as exc:
        StripeWebhookEvent.objects.filter(pk=webhook_event.pk).update(
            status=StripeWebhookEvent.STATUS_FAILED,
            last_error=str(exc)[:2000],
        )
        return 500

    StripeWebhookEvent.objects.filter(pk=webhook_event.pk).update(
        status=StripeWebhookEvent.STATUS_PROCESSED,
        processed_at=timezone.now(),
        last_error="",
    )
    return 200

