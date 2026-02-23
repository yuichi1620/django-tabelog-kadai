from django.conf import settings
from django.core import signing
from django.core.mail import send_mail
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.contrib.auth.tokens import default_token_generator


def send_signup_verification_email(request, user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    verify_url = request.build_absolute_uri(
        reverse("restaurants:verify_email", kwargs={"uidb64": uid, "token": token})
    )
    send_mail(
        subject="【NAGOYAMESHI】メール認証のご案内",
        message=f"以下のURLにアクセスして会員登録を完了してください。\n{verify_url}",
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@example.com"),
        recipient_list=[user.email],
        fail_silently=False,
    )


def build_email_change_token(*, user_id, new_email, nonce):
    return signing.dumps(
        {
            "uid": user_id,
            "email": new_email,
            "nonce": str(nonce),
        },
        salt="email-change",
    )


def send_email_change_verification_email(request, *, new_email, token):
    verify_url = request.build_absolute_uri(
        reverse("restaurants:verify_email_change", kwargs={"token": token})
    )
    send_mail(
        subject="【NAGOYAMESHI】メールアドレス変更の確認",
        message=(
            "以下のURLにアクセスしてメールアドレス変更を完了してください。\n"
            f"{verify_url}"
        ),
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@example.com"),
        recipient_list=[new_email],
        fail_silently=False,
    )

