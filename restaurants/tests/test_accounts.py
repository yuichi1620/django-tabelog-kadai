from urllib.parse import urlparse
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse

from restaurants.models import Member


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

    @override_settings(AUTO_ACTIVATE_ON_EMAIL_FAILURE=True)
    @patch("app_accounts.services.mail_service.send_mail", side_effect=Exception("smtp down"))
    def test_signup_auto_activates_when_mail_fails(self, _mock_send_mail):
        response = self.client.post(
            reverse("restaurants:signup"),
            {
                "full_name": "障害時ユーザー",
                "email": "mailfail_signup@example.com",
                "password1": "ComplexPass123",
                "password2": "ComplexPass123",
                "accept_terms": "on",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        user = get_user_model().objects.get(email="mailfail_signup@example.com")
        self.assertTrue(user.is_active)
        self.assertContains(response, "現在メール送信に障害があるため、登録を有効化しました。")

    @override_settings(AUTO_ACTIVATE_ON_EMAIL_FAILURE=True)
    @patch("app_accounts.services.mail_service.send_mail", side_effect=Exception("smtp down"))
    def test_resend_auto_activates_when_mail_fails(self, _mock_send_mail):
        user = get_user_model().objects.create_user(
            username="mailfail_resend@example.com",
            email="mailfail_resend@example.com",
            password="pass12345",
            is_active=False,
        )
        Member.objects.create(user=user, full_name="Mail Fail")

        response = self.client.post(
            reverse("restaurants:resend_verification_email"),
            {"email": "mailfail_resend@example.com"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertContains(response, "現在メール送信に障害があるため、アカウントを有効化しました。")


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

