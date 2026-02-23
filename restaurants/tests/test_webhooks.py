import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse

from restaurants.models import Member, StripeWebhookEvent


class StripeWebhookIdempotencyTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="webhook@example.com",
            email="webhook@example.com",
            password="pass12345",
        )
        self.member = Member.objects.create(user=self.user, full_name="Webhook User")

    @override_settings(DEBUG=True, STRIPE_WEBHOOK_SECRET="")
    def test_same_event_id_is_processed_once(self):
        payload = {
            "id": "evt_test_idempotent_001",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "customer": "cus_test_001",
                    "subscription": "sub_test_001",
                    "metadata": {"user_id": str(self.user.id)},
                }
            },
        }

        url = reverse("restaurants:stripe_webhook")
        first = self.client.post(url, data=json.dumps(payload), content_type="application/json")
        second = self.client.post(url, data=json.dumps(payload), content_type="application/json")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(StripeWebhookEvent.objects.filter(event_id="evt_test_idempotent_001").count(), 1)

        self.member.refresh_from_db()
        self.assertEqual(self.member.plan_status, Member.PLAN_PAID)
        self.assertEqual(self.member.stripe_customer_id, "cus_test_001")


class StripeWebhookSecurityTests(TestCase):
    @override_settings(DEBUG=False, STRIPE_WEBHOOK_SECRET="")
    def test_webhook_rejects_unsigned_payload_in_production(self):
        payload = {
            "id": "evt_test_unsigned_001",
            "type": "checkout.session.completed",
            "data": {"object": {"customer": "cus_test_001"}},
        }
        response = self.client.post(
            reverse("restaurants:stripe_webhook"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

