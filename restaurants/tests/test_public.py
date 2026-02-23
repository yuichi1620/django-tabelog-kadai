from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from restaurants.models import Category, Favorite, Member, Reservation, Restaurant, Review


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

