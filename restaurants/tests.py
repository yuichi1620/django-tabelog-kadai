from datetime import timedelta
import json
from urllib.parse import urlparse
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.db import IntegrityError
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse
from django.utils import timezone

from .forms import MemberForm
from .models import Category, Favorite, Member, Reservation, Restaurant, Review, StripeWebhookEvent


class RestaurantListViewTests(TestCase):
    def setUp(self):
        self.category_a = Category.objects.create(name="和食")
        self.category_b = Category.objects.create(name="カフェ")

        self.restaurant_old = Restaurant.objects.create(
            name="古い店",
            address="名古屋駅",
            category=self.category_a,
            budget_min=1000,
            budget_max=3000,
        )
        self.restaurant_new = Restaurant.objects.create(
            name="新しい店",
            address="栄",
            category=self.category_a,
            budget_min=1000,
            budget_max=3000,
        )
        self.restaurant_no_review = Restaurant.objects.create(
            name="レビューなし店",
            address="伏見",
            category=self.category_b,
            budget_min=800,
            budget_max=2000,
        )

        now = timezone.now()
        Restaurant.objects.filter(pk=self.restaurant_old.pk).update(created_at=now - timedelta(days=2))
        Restaurant.objects.filter(pk=self.restaurant_new.pk).update(created_at=now - timedelta(days=1))
        Restaurant.objects.filter(pk=self.restaurant_no_review.pk).update(created_at=now)

        user = get_user_model().objects.create_user(
            username="reviewer@example.com", email="reviewer@example.com", password="pass12345"
        )
        Member.objects.create(user=user, full_name="Reviewer", plan_status=Member.PLAN_PAID)
        Review.objects.create(
            user=user,
            restaurant=self.restaurant_old,
            rating_atmosphere=2,
            rating_taste=2,
            rating_price=2,
            rating_service=2,
            comment="old",
        )
        Review.objects.create(
            user=user,
            restaurant=self.restaurant_new,
            rating_atmosphere=5,
            rating_taste=5,
            rating_price=5,
            rating_service=5,
            comment="new",
        )
        Favorite.objects.create(user=user, restaurant=self.restaurant_new)

    def test_list_sort_new_orders_by_created_at_desc(self):
        response = self.client.get(reverse("restaurants:list"), {"sort": "new"})
        self.assertEqual(response.status_code, 200)

        restaurants = list(response.context["restaurants"])
        self.assertEqual(restaurants[0].pk, self.restaurant_no_review.pk)

    def test_list_sort_rating_orders_by_avg_rating_desc(self):
        response = self.client.get(reverse("restaurants:list"), {"sort": "rating"})
        self.assertEqual(response.status_code, 200)

        restaurants = list(response.context["restaurants"])
        self.assertEqual(restaurants[0].pk, self.restaurant_new.pk)

    def test_list_sort_popular_orders_by_favorite_count_desc(self):
        response = self.client.get(reverse("restaurants:list"), {"sort": "popular"})
        self.assertEqual(response.status_code, 200)
        restaurants = list(response.context["restaurants"])
        self.assertEqual(restaurants[0].pk, self.restaurant_new.pk)

    def test_list_sort_price_low_orders_by_budget_min_asc(self):
        response = self.client.get(reverse("restaurants:list"), {"sort": "price_low"})
        self.assertEqual(response.status_code, 200)
        restaurants = list(response.context["restaurants"])
        self.assertEqual(restaurants[0].pk, self.restaurant_no_review.pk)

    def test_list_sort_price_high_orders_by_budget_max_desc(self):
        response = self.client.get(reverse("restaurants:list"), {"sort": "price_high"})
        self.assertEqual(response.status_code, 200)
        restaurants = list(response.context["restaurants"])
        self.assertEqual(restaurants[0].pk, self.restaurant_new.pk)

    def test_non_public_review_is_hidden_from_public_list(self):
        review = Review.objects.get(restaurant=self.restaurant_old)
        review.is_public = False
        review.save(update_fields=["is_public"])

        response = self.client.get(reverse("restaurants:list"), {"sort": "rating"})
        self.assertEqual(response.status_code, 200)
        restaurants = list(response.context["restaurants"])
        self.assertEqual(restaurants[0].pk, self.restaurant_new.pk)


class PaidRestrictionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="user1@example.com", email="user1@example.com", password="pass12345"
        )
        Member.objects.create(user=self.user, full_name="User1", plan_status=Member.PLAN_FREE)
        self.category = Category.objects.create(name="焼肉")
        self.restaurant = Restaurant.objects.create(
            name="テスト店",
            address="名古屋市",
            category=self.category,
            budget_min=1000,
            budget_max=4000,
        )

    def test_free_member_cannot_create_review(self):
        self.client.login(username="user1@example.com", password="pass12345")
        response = self.client.post(
            reverse("restaurants:review_create", kwargs={"pk": self.restaurant.pk}),
            {
                "rating_atmosphere": "5",
                "rating_taste": "5",
                "rating_price": "5",
                "rating_service": "5",
                "comment": "great",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("restaurants:upgrade_membership"), fetch_redirect_response=False)

    def test_paid_member_can_create_and_delete_review(self):
        member = Member.objects.get(user=self.user)
        member.plan_status = Member.PLAN_PAID
        member.save(update_fields=["plan_status"])

        self.client.login(username="user1@example.com", password="pass12345")
        self.client.post(
            reverse("restaurants:review_create", kwargs={"pk": self.restaurant.pk}),
            {
                "rating_atmosphere": "4",
                "rating_taste": "4",
                "rating_price": "4",
                "rating_service": "4",
                "comment": "first",
            },
        )
        self.assertEqual(Review.objects.count(), 1)

        self.client.post(reverse("restaurants:review_delete", kwargs={"pk": self.restaurant.pk}))
        self.assertEqual(Review.objects.count(), 0)


class ReservationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="paid@example.com", email="paid@example.com", password="pass12345"
        )
        Member.objects.create(user=self.user, full_name="Paid", plan_status=Member.PLAN_PAID)
        self.category = Category.objects.create(name="寿司")
        self.restaurant = Restaurant.objects.create(
            name="寿司屋",
            address="名古屋市",
            category=self.category,
            budget_min=3000,
            budget_max=8000,
        )
        self.client.login(username="paid@example.com", password="pass12345")

    def test_create_and_cancel_reservation(self):
        reserved_at = (timezone.now() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")
        response = self.client.post(
            reverse("restaurants:reservation_create", kwargs={"pk": self.restaurant.pk}),
            {"reserved_at": reserved_at, "people_count": 2},
        )
        self.assertEqual(response.status_code, 302)
        reservation = Reservation.objects.get(user=self.user)
        self.assertEqual(reservation.status, Reservation.STATUS_ACTIVE)

        cancel_response = self.client.post(reverse("restaurants:reservation_cancel", kwargs={"pk": reservation.pk}))
        self.assertEqual(cancel_response.status_code, 302)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.STATUS_CANCELED)


class ModelConstraintTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="u1@example.com", email="u1@example.com", password="pass12345"
        )
        Member.objects.create(user=self.user, full_name="u1")
        self.category = Category.objects.create(name="ラーメン")
        self.restaurant = Restaurant.objects.create(
            name="制約確認店",
            address="名古屋市中区",
            category=self.category,
            budget_min=900,
            budget_max=1500,
        )

    def test_review_unique_constraint(self):
        Review.objects.create(
            user=self.user,
            restaurant=self.restaurant,
            rating_atmosphere=4,
            rating_taste=4,
            rating_price=4,
            rating_service=4,
            comment="",
        )
        with self.assertRaises(IntegrityError):
            Review.objects.create(
                user=self.user,
                restaurant=self.restaurant,
                rating_atmosphere=5,
                rating_taste=5,
                rating_price=5,
                rating_service=5,
                comment="",
            )

    def test_favorite_unique_constraint(self):
        Favorite.objects.create(user=self.user, restaurant=self.restaurant)
        with self.assertRaises(IntegrityError):
            Favorite.objects.create(user=self.user, restaurant=self.restaurant)


class MemberFormValidationTests(TestCase):
    def test_phone_number_validation(self):
        form = MemberForm(data={"full_name": "山田", "phone_number": "abc-1234", "postal_code": "123-4567", "address": "名古屋"})
        self.assertFalse(form.is_valid())
        self.assertIn("phone_number", form.errors)

    def test_postal_code_validation(self):
        form = MemberForm(data={"full_name": "山田", "phone_number": "090-1234-5678", "postal_code": "1234", "address": "名古屋"})
        self.assertFalse(form.is_valid())
        self.assertIn("postal_code", form.errors)

    def test_member_form_valid_data(self):
        form = MemberForm(data={"full_name": "山田", "phone_number": "090-1234-5678", "postal_code": "123-4567", "address": "名古屋市中区"})
        self.assertTrue(form.is_valid())


class SignUpFlowTests(TestCase):
    def test_signup_sends_verification_email(self):
        response = self.client.post(
            reverse("restaurants:signup"),
            {
                "full_name": "新規ユーザー",
                "email": "new_user@example.com",
                "password1": "ComplexPass123",
                "password2": "ComplexPass123",
                "accept_terms": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(get_user_model().objects.filter(email="new_user@example.com").exists())
        self.assertEqual(len(mail.outbox), 1)

    def test_resend_verification_email_for_inactive_user(self):
        user = get_user_model().objects.create_user(
            username="inactive@example.com",
            email="inactive@example.com",
            password="pass12345",
            is_active=False,
        )
        Member.objects.create(user=user, full_name="Inactive User")

        response = self.client.post(
            reverse("restaurants:resend_verification_email"),
            {"email": "inactive@example.com"},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "認証メールを再送しました")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/accounts/verify/", mail.outbox[0].body)

    def test_inactive_user_login_shows_verification_message(self):
        get_user_model().objects.create_user(
            username="inactive_login@example.com",
            email="inactive_login@example.com",
            password="pass12345",
            is_active=False,
        )

        response = self.client.post(
            reverse("login"),
            {"username": "inactive_login@example.com", "password": "pass12345"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "メール認証が完了していません")


class EmailChangeVerificationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="old@example.com",
            email="old@example.com",
            password="pass12345",
            first_name="旧名前",
        )
        Member.objects.create(user=self.user, full_name="旧名前")
        self.client.login(username="old@example.com", password="pass12345")

    def test_email_change_requires_verification(self):
        response = self.client.post(
            reverse("restaurants:member_account_edit"),
            {"full_name": "新名前", "email": "new@example.com"},
        )
        self.assertEqual(response.status_code, 200)

        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "新名前")
        self.assertEqual(self.user.email, "old@example.com")
        self.assertEqual(len(mail.outbox), 1)

        verify_url = mail.outbox[0].body.strip().splitlines()[-1]
        path = urlparse(verify_url).path
        verify_response = self.client.get(path)
        self.assertEqual(verify_response.status_code, 200)

        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "new@example.com")
        self.assertEqual(self.user.username, "new@example.com")

    def test_resend_invalidates_old_email_change_link(self):
        first = self.client.post(
            reverse("restaurants:member_account_edit"),
            {"full_name": "新名前", "email": "new1@example.com"},
        )
        self.assertEqual(first.status_code, 200)
        first_url = mail.outbox[-1].body.strip().splitlines()[-1]
        first_path = urlparse(first_url).path

        second = self.client.post(
            reverse("restaurants:member_account_edit"),
            {"full_name": "新名前", "email": "new2@example.com"},
        )
        self.assertEqual(second.status_code, 200)
        second_url = mail.outbox[-1].body.strip().splitlines()[-1]
        second_path = urlparse(second_url).path

        old_link_response = self.client.get(first_path, follow=True)
        self.assertEqual(old_link_response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "old@example.com")

        new_link_response = self.client.get(second_path)
        self.assertEqual(new_link_response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "new2@example.com")


class StripeWebhookIdempotencyTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="webhook@example.com",
            email="webhook@example.com",
            password="pass12345",
        )
        self.member = Member.objects.create(user=self.user, full_name="Webhook User")

    @override_settings(STRIPE_WEBHOOK_SECRET="")
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
    @patch("restaurants.views.stripe.checkout.Session.retrieve")
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
