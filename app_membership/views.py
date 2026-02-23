import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from restaurants.constants import MONTHLY_FEE
from restaurants.models import Member
from app_membership.services import stripe_service

logger = logging.getLogger(__name__)


@login_required
def upgrade_membership(request):
    member, _ = Member.objects.get_or_create(user=request.user, defaults={"full_name": request.user.first_name})

    return render(
        request,
        "restaurants/upgrade_membership.html",
        {
            "member": member,
            "monthly_fee": MONTHLY_FEE,
            "stripe_ready": bool(settings.STRIPE_SECRET_KEY and settings.STRIPE_PRICE_ID),
        },
    )


@login_required
@require_POST
def create_checkout_session(request):
    if not settings.STRIPE_SECRET_KEY or not settings.STRIPE_PRICE_ID:
        messages.error(request, "Stripe設定が不足しています。運営者に連絡してください。")
        return redirect("restaurants:upgrade_membership")

    member, _ = Member.objects.get_or_create(user=request.user, defaults={"full_name": request.user.first_name})

    try:
        session_url = stripe_service.create_checkout_session_url(member=member, user=request.user)
    except Exception:
        logger.exception("Failed to create Stripe checkout session: user_id=%s", request.user.id)
        messages.error(request, "決済画面の作成に失敗しました。時間をおいて再度お試しください。")
        return redirect("restaurants:upgrade_membership")

    return redirect(session_url, permanent=False)


@login_required
def billing_success(request):
    session_id = request.GET.get("session_id", "").strip()
    if session_id and settings.STRIPE_SECRET_KEY:
        try:
            result = stripe_service.process_billing_success(user=request.user, session_id=session_id)
            if result["status"] == "foreign_user":
                messages.error(request, "この決済結果は現在のログインユーザーでは確認できません。")
                return redirect("restaurants:upgrade_membership")
            if result["status"] == "customer_mismatch":
                messages.error(request, "決済情報の整合性確認に失敗しました。運営者に連絡してください。")
                return redirect("restaurants:upgrade_membership")
        except Exception:
            # Webhookが正常に到達していればこのフォールバックが失敗しても問題ない。
            logger.exception("Failed to process billing_success fallback: user_id=%s", request.user.id)

    messages.success(request, "決済が完了しました。反映に数秒かかる場合があります。")
    return render(request, "restaurants/billing_success.html")


@login_required
@require_POST
def create_billing_portal_session(request):
    member, _ = Member.objects.get_or_create(user=request.user)
    try:
        session_url = stripe_service.create_billing_portal_session_url(member=member, user=request.user)
    except Exception:
        logger.exception("Failed to create Stripe billing portal session: user_id=%s", request.user.id)
        messages.error(request, "カード情報管理ページの作成に失敗しました。時間をおいて再度お試しください。")
        return redirect("restaurants:upgrade_membership")

    return redirect(session_url, permanent=False)


@login_required
@require_POST
def cancel_membership(request):
    member, _ = Member.objects.get_or_create(user=request.user)
    try:
        result = stripe_service.cancel_membership(member)
    except Exception:
        logger.exception("Failed to cancel Stripe subscription: user_id=%s", request.user.id)
        messages.error(request, "解約処理に失敗しました。時間をおいて再度お試しください。")
        return redirect("restaurants:mypage")

    if result == "scheduled":
        messages.success(request, "サブスク解約を受け付けました。現在の契約期間終了後に解約されます。")
    else:
        messages.success(request, "有料会員を解約しました。")
    return redirect("restaurants:mypage")


@login_required
def payment_method_edit(request):
    member, _ = Member.objects.get_or_create(user=request.user)
    return render(request, "restaurants/payment_method_form.html", {"member": member})


@login_required
@require_POST
def payment_method_delete(request):
    messages.info(request, "カード情報削除はStripeのカスタマーポータルから行ってください。")
    return redirect("restaurants:payment_method_edit")
