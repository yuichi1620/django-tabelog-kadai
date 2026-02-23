from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase

from restaurants.forms import MemberForm
from restaurants.models import Category, Favorite, Member, Restaurant, Review


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

