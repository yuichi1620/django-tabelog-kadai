from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse

from restaurants.models import Category, Member, Restaurant


class SecurityRegressionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="secure1@example.com",
            email="secure1@example.com",
            password="pass12345",
        )
        self.other_user = get_user_model().objects.create_user(
            username="secure2@example.com",
            email="secure2@example.com",
            password="pass12345",
        )
        Member.objects.create(user=self.user, full_name="Secure1", plan_status=Member.PLAN_PAID)
        Member.objects.create(user=self.other_user, full_name="Secure2", plan_status=Member.PLAN_PAID)
        category = Category.objects.create(name="セキュリティ")
        self.restaurant = Restaurant.objects.create(
            name="検証店",
            address="名古屋市中村区",
            category=category,
            budget_min=1000,
            budget_max=3000,
        )
        self.client.login(username="secure1@example.com", password="pass12345")

    def test_toggle_favorite_ignores_external_next_url(self):
        response = self.client.post(
            reverse("restaurants:toggle_favorite", kwargs={"pk": self.restaurant.pk}),
            {"next": "https://example.com/phishing"},
        )
        self.assertRedirects(
            response,
            reverse("restaurants:detail", kwargs={"pk": self.restaurant.pk}),
            fetch_redirect_response=False,
        )

    @override_settings(STRIPE_SECRET_KEY="sk_test_dummy")
    @patch("app_membership.services.stripe_service.stripe.checkout.Session.retrieve")
    def test_billing_success_rejects_foreign_user_session(self, mock_retrieve):
        member = Member.objects.get(user=self.user)
        member.plan_status = Member.PLAN_FREE
        member.save(update_fields=["plan_status"])
        mock_retrieve.return_value = {
            "payment_status": "paid",
            "customer": "cus_foreign",
            "subscription": "sub_foreign",
            "metadata": {"user_id": str(self.other_user.id)},
        }
        response = self.client.get(reverse("restaurants:billing_success"), {"session_id": "cs_test_foreign"})
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response,
            reverse("restaurants:upgrade_membership"),
            fetch_redirect_response=False,
        )
        member.refresh_from_db()
        self.assertEqual(member.plan_status, Member.PLAN_FREE)
        self.assertEqual(member.stripe_customer_id, "")

