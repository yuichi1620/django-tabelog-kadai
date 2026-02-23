import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.tokens import default_token_generator
from django.core import signing
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode

from app_accounts.forms import ResendVerificationEmailForm, SignUpForm
from app_accounts.services.mail_service import send_signup_verification_email
from restaurants.models import Member

EMAIL_CHANGE_TOKEN_MAX_AGE = getattr(settings, "EMAIL_CHANGE_TOKEN_MAX_AGE", 60 * 60 * 24)
logger = logging.getLogger(__name__)


def _activate_user_without_email_verification(user):
    if user.is_active:
        return
    user.is_active = True
    user.save(update_fields=["is_active"])


def signup(request):
    if request.user.is_authenticated:
        return redirect("restaurants:list")

    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            Member.objects.get_or_create(
                user=user,
                defaults={"full_name": form.cleaned_data["full_name"].strip()},
            )

            try:
                send_signup_verification_email(request, user)
                sent = True
            except Exception:
                logger.exception("Failed to send signup verification email. user_id=%s", user.id)
                sent = False
            if not sent and settings.AUTO_ACTIVATE_ON_EMAIL_FAILURE:
                _activate_user_without_email_verification(user)
                messages.warning(
                    request,
                    "現在メール送信に障害があるため、登録を有効化しました。ログインしてください。",
                )
                return redirect("login")

            context = {"email": user.email, "email_send_failed": not sent}
            return render(request, "registration/verification_sent.html", context)
    else:
        form = SignUpForm()

    return render(request, "registration/signup.html", {"form": form})


def resend_verification_email(request):
    if request.method == "POST":
        form = ResendVerificationEmailForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            user_model = get_user_model()
            user = user_model.objects.filter(email__iexact=email).order_by("-id").first()

            sent = True
            if user and not user.is_active:
                try:
                    send_signup_verification_email(request, user)
                except Exception:
                    logger.exception("Failed to resend signup verification email. user_id=%s", user.id)
                    sent = False
                if not sent and settings.AUTO_ACTIVATE_ON_EMAIL_FAILURE:
                    _activate_user_without_email_verification(user)
                    messages.warning(
                        request,
                        "現在メール送信に障害があるため、アカウントを有効化しました。ログインできます。",
                    )
                    return redirect("login")

            if sent:
                messages.success(request, "該当する未認証アカウントがある場合、認証メールを再送しました。")
            else:
                messages.error(request, "認証メールの送信に失敗しました。時間をおいて再度お試しください。")
            return redirect("restaurants:resend_verification_email")
    else:
        form = ResendVerificationEmailForm()

    return render(request, "registration/resend_verification_email.html", {"form": form})


def verify_email(request, uidb64, token):
    User = get_user_model()
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        raise Http404("Invalid verification link")

    if not default_token_generator.check_token(user, token):
        messages.error(request, "認証リンクが無効です。")
        return redirect("restaurants:signup")

    user.is_active = True
    user.save(update_fields=["is_active"])
    login(request, user)
    messages.success(request, "メール認証が完了しました。")
    return render(request, "registration/verify_success.html")


def verify_email_change(request, token):
    User = get_user_model()
    try:
        payload = signing.loads(
            token,
            salt="email-change",
            max_age=EMAIL_CHANGE_TOKEN_MAX_AGE,
        )
    except signing.SignatureExpired:
        messages.error(request, "認証リンクの有効期限が切れています。")
        return redirect("restaurants:member_account_edit")
    except signing.BadSignature:
        messages.error(request, "認証リンクが無効です。")
        return redirect("restaurants:member_account_edit")

    user_id = payload.get("uid")
    new_email = (payload.get("email") or "").strip().lower()
    nonce = payload.get("nonce")
    if not user_id or not new_email:
        messages.error(request, "認証リンクが無効です。")
        return redirect("restaurants:member_account_edit")

    member = Member.objects.filter(user_id=user_id).first()
    if not member:
        messages.error(request, "会員情報が見つかりません。")
        return redirect("restaurants:member_account_edit")

    if not member.pending_email or member.pending_email.lower() != new_email:
        messages.error(request, "この認証リンクはすでに無効化されています。")
        return redirect("restaurants:member_account_edit")

    if not member.email_change_token or str(member.email_change_token) != str(nonce):
        messages.error(request, "この認証リンクは再発行により無効化されています。")
        return redirect("restaurants:member_account_edit")

    if User.objects.filter(email__iexact=new_email).exclude(pk=user_id).exists():
        messages.error(request, "このメールアドレスはすでに利用されています。")
        return redirect("restaurants:member_account_edit")

    user = get_object_or_404(User, pk=user_id)
    user.email = new_email
    user.username = new_email
    user.save(update_fields=["email", "username"])
    member.pending_email = ""
    member.email_change_requested_at = None
    member.email_change_token = None
    member.save(update_fields=["pending_email", "email_change_requested_at", "email_change_token"])
    messages.success(request, "メールアドレスの変更が完了しました。")
    return render(request, "registration/verify_success.html", {"email_change": True})
