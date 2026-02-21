from datetime import datetime
import json

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.core import signing
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Avg, Count, F, Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import stripe

from .forms import AccountUpdateForm, MemberForm, ReservationForm, SignUpForm
from .models import (
    Category,
    Coupon,
    Favorite,
    Member,
    PaymentMethod,
    Reservation,
    Restaurant,
    Review,
    SiteSetting,
    StripeWebhookEvent,
    UserCoupon,
)

REVIEW_COMMENT_MAX_LENGTH = 500
MONTHLY_FEE = 300
EMAIL_CHANGE_TOKEN_MAX_AGE = getattr(settings, "EMAIL_CHANGE_TOKEN_MAX_AGE", 60 * 60 * 24)

stripe.api_key = settings.STRIPE_SECRET_KEY


def paid_member_required(view_func):
    @login_required
    def _wrapped(request, *args, **kwargs):
        member, _ = Member.objects.get_or_create(user=request.user)
        if not member.is_paid:
            messages.info(request, "この機能は有料会員限定です。")
            return redirect("restaurants:upgrade_membership")
        return view_func(request, *args, **kwargs)

    return _wrapped


# ===== 認証 =====

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

            return render(request, "registration/verification_sent.html", {"email": user.email})
    else:
        form = SignUpForm()

    return render(request, "registration/signup.html", {"form": form})


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


# ===== レビュー =====

@paid_member_required
@require_POST
def review_create(request, pk):
    restaurant = get_object_or_404(Restaurant, pk=pk)

    rating = request.POST.get("rating", "").strip()
    comment = request.POST.get("comment", "").strip()

    if not rating.isdigit() or not (1 <= int(rating) <= 5):
        messages.error(request, "評価は1〜5で入力してな。")
        return redirect("restaurants:detail", pk=pk)

    if len(comment) > REVIEW_COMMENT_MAX_LENGTH:
        messages.error(request, f"レビュー本文は{REVIEW_COMMENT_MAX_LENGTH}文字以内で入力してな。")
        return redirect("restaurants:detail", pk=pk)

    review, created = Review.objects.update_or_create(
        user=request.user,
        restaurant=restaurant,
        defaults={"rating": int(rating), "comment": comment},
    )

    messages.success(request, "レビュー投稿できたで！" if created else "レビュー更新できたで！")
    return redirect("restaurants:detail", pk=pk)


@paid_member_required
@require_POST
def review_delete(request, pk):
    restaurant = get_object_or_404(Restaurant, pk=pk)

    review = Review.objects.filter(user=request.user, restaurant=restaurant).first()
    if not review:
        messages.info(request, "削除するレビューが見つからんかったで。")
        return redirect("restaurants:detail", pk=pk)

    review.delete()
    messages.success(request, "レビュー削除できたで！")
    return redirect("restaurants:detail", pk=pk)


# ===== お気に入り =====

@paid_member_required
def favorite_list(request):
    favorites = (
        Favorite.objects.select_related("restaurant", "restaurant__category")
        .filter(user=request.user)
        .order_by("-id")
    )
    restaurants = [f.restaurant for f in favorites]
    return render(request, "restaurants/favorite_list.html", {"restaurants": restaurants})


@paid_member_required
@require_POST
def toggle_favorite(request, pk):
    restaurant = get_object_or_404(Restaurant, pk=pk)

    favorite, created = Favorite.objects.get_or_create(
        user=request.user,
        restaurant=restaurant,
    )
    if not created:
        favorite.delete()

    next_url = request.POST.get("next")
    if next_url:
        return redirect(next_url)

    return redirect("restaurants:detail", pk=pk)


# ===== 店舗一覧（検索＋ソート＋ページネーション） =====

def restaurant_list(request):
    q = request.GET.get("q", "").strip()
    category_id = request.GET.get("category", "").strip()
    budget = request.GET.get("budget", "").strip()
    sort = request.GET.get("sort", "").strip()

    restaurants = Restaurant.objects.select_related("category").all()

    if q:
        restaurants = restaurants.filter(
            Q(name__icontains=q) | Q(address__icontains=q) | Q(category__name__icontains=q)
        )

    if category_id.isdigit():
        restaurants = restaurants.filter(category_id=int(category_id))

    if budget.isdigit():
        b = int(budget)
        restaurants = restaurants.filter(budget_max__lte=b)

    restaurants = restaurants.annotate(
        avg_rating=Avg("reviews__rating", filter=Q(reviews__is_public=True)),
        review_count=Count("reviews", filter=Q(reviews__is_public=True), distinct=True),
        favorite_count=Count("favorite", distinct=True),
    )

    if sort == "new":
        restaurants = restaurants.order_by("-created_at")
    elif sort == "rating":
        restaurants = restaurants.order_by(F("avg_rating").desc(nulls_last=True), "-created_at")
    elif sort == "popular":
        restaurants = restaurants.order_by("-favorite_count", F("avg_rating").desc(nulls_last=True), "-created_at")
    elif sort == "price_low":
        restaurants = restaurants.order_by("budget_min", "budget_max", "-created_at")
    elif sort == "price_high":
        restaurants = restaurants.order_by("-budget_max", "-budget_min", "-created_at")
    else:
        restaurants = restaurants.order_by("-created_at")

    paginator = Paginator(restaurants, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    categories = Category.objects.all().order_by("name")
    coupon_restaurants = (
        Restaurant.objects.select_related("category")
        .filter(coupons__is_active=True)
        .annotate(
            active_coupon_count=Count("coupons", filter=Q(coupons__is_active=True), distinct=True),
            avg_rating=Avg("reviews__rating", filter=Q(reviews__is_public=True)),
        )
        .order_by("-active_coupon_count", F("avg_rating").desc(nulls_last=True), "-created_at")
        .distinct()[:8]
    )
    top_rated_restaurants = (
        Restaurant.objects.select_related("category")
        .annotate(
            avg_rating=Avg("reviews__rating", filter=Q(reviews__is_public=True)),
            review_count=Count("reviews", filter=Q(reviews__is_public=True), distinct=True),
        )
        .filter(review_count__gt=0)
        .order_by(F("avg_rating").desc(nulls_last=True), "-review_count", "-created_at")[:5]
    )
    new_arrival_restaurants = (
        Restaurant.objects.select_related("category")
        .annotate(
            avg_rating=Avg("reviews__rating", filter=Q(reviews__is_public=True)),
            review_count=Count("reviews", filter=Q(reviews__is_public=True), distinct=True),
        )
        .order_by("-created_at")[:8]
    )

    context = {
        "restaurants": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "categories": categories,
        "coupon_restaurants": coupon_restaurants,
        "top_rated_restaurants": top_rated_restaurants,
        "new_arrival_restaurants": new_arrival_restaurants,
        "q": q,
        "category_id": category_id,
        "budget": budget,
        "sort": sort,
    }
    return render(request, "restaurants/restaurant_list.html", context)


# ===== 店舗詳細 =====

def restaurant_detail(request, pk):
    restaurant = get_object_or_404(
        Restaurant.objects.select_related("category").prefetch_related("reviews", "coupons"),
        pk=pk,
    )

    reviews = restaurant.reviews.filter(is_public=True).order_by("-created_at")
    avg_rating = reviews.aggregate(avg=Avg("rating"))["avg"]

    is_favorite = False
    my_review = None
    member = None
    reservation_form = ReservationForm()
    coupons = restaurant.coupons.filter(is_active=True)
    my_coupon_ids = set()

    if request.user.is_authenticated:
        member, _ = Member.objects.get_or_create(user=request.user)
        is_favorite = Favorite.objects.filter(user=request.user, restaurant=restaurant).exists()
        my_review = Review.objects.filter(user=request.user, restaurant=restaurant).first()
        my_coupon_ids = set(
            UserCoupon.objects.filter(user=request.user, coupon__restaurant=restaurant).values_list(
                "coupon_id", flat=True
            )
        )

    context = {
        "restaurant": restaurant,
        "reviews": reviews,
        "avg_rating": avg_rating,
        "is_favorite": is_favorite,
        "my_review": my_review,
        "member": member,
        "reservation_form": reservation_form,
        "coupons": coupons,
        "my_coupon_ids": my_coupon_ids,
    }
    return render(request, "restaurants/restaurant_detail.html", context)


# ===== 予約 =====

@paid_member_required
@require_POST
def reservation_create(request, pk):
    restaurant = get_object_or_404(Restaurant, pk=pk)
    form = ReservationForm(request.POST)

    if not form.is_valid():
        messages.error(request, "予約内容に不備があります。")
        return redirect("restaurants:detail", pk=pk)

    reservation = form.save(commit=False)
    reservation.user = request.user
    reservation.restaurant = restaurant
    reservation.status = Reservation.STATUS_ACTIVE
    reservation.save()

    send_mail(
        subject="【NAGOYAMESHI】予約完了のお知らせ",
        message=(
            f"{restaurant.name} の予約が完了しました。\n"
            f"日時: {reservation.reserved_at}\n"
            f"人数: {reservation.people_count}名"
        ),
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@example.com"),
        recipient_list=[request.user.email] if request.user.email else [],
        fail_silently=True,
    )

    messages.success(request, "予約が完了しました。")
    return redirect("restaurants:reservation_list")


@paid_member_required
def reservation_list(request):
    reservations = (
        Reservation.objects.select_related("restaurant")
        .filter(user=request.user)
        .order_by("-reserved_at")
    )
    return render(request, "restaurants/reservation_list.html", {"reservations": reservations})


@paid_member_required
@require_POST
def reservation_cancel(request, pk):
    reservation = get_object_or_404(Reservation, pk=pk, user=request.user)

    if reservation.reserved_at <= timezone.now():
        messages.error(request, "予約日時を過ぎた予約はキャンセルできません。")
        return redirect("restaurants:reservation_list")

    reservation.status = Reservation.STATUS_CANCELED
    reservation.save(update_fields=["status"])
    messages.success(request, "予約をキャンセルしました。")
    return redirect("restaurants:reservation_list")


# ===== クーポン =====

@paid_member_required
@require_POST
def coupon_use(request, pk):
    coupon = get_object_or_404(Coupon, pk=pk, is_active=True)
    user_coupon, _ = UserCoupon.objects.get_or_create(user=request.user, coupon=coupon)

    if user_coupon.used_at:
        messages.info(request, "このクーポンはすでに使用済みです。")
        return redirect("restaurants:detail", pk=coupon.restaurant_id)

    user_coupon.used_at = timezone.now()
    user_coupon.save(update_fields=["used_at"])
    messages.success(request, "クーポンを使用しました。")
    return redirect("restaurants:detail", pk=coupon.restaurant_id)


# ===== 会員情報 =====

@login_required
def member_profile_edit(request):
    member, _ = Member.objects.get_or_create(user=request.user, defaults={"full_name": request.user.first_name})

    if request.method == "POST":
        form = MemberForm(request.POST, instance=member)
        if form.is_valid():
            member = form.save()
            request.user.first_name = member.full_name
            request.user.save(update_fields=["first_name"])
            messages.success(request, "会員情報を更新しました。")
            return redirect("restaurants:member_profile_edit")
    else:
        form = MemberForm(instance=member)

    return render(request, "registration/member_profile_form.html", {"form": form, "member": member})


@login_required
def member_account_edit(request):
    initial = {
        "full_name": request.user.first_name,
        "email": request.user.email,
    }

    if request.method == "POST":
        form = AccountUpdateForm(request.POST, user=request.user)
        if form.is_valid():
            new_full_name = form.cleaned_data["full_name"].strip()
            new_email = form.cleaned_data["email"].strip().lower()
            current_email = (request.user.email or "").strip().lower()

            request.user.first_name = new_full_name
            request.user.save(update_fields=["first_name"])

            member, _ = Member.objects.get_or_create(user=request.user)
            member.full_name = request.user.first_name
            update_fields = ["full_name"]

            if new_email != current_email:
                member.pending_email = new_email
                member.issue_email_change_token()
                update_fields.extend(["pending_email", "email_change_requested_at", "email_change_token"])
                member.save(update_fields=update_fields)

                token = signing.dumps(
                    {
                        "uid": request.user.pk,
                        "email": new_email,
                        "nonce": str(member.email_change_token),
                    },
                    salt="email-change",
                )
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
                messages.info(request, "新しいメールアドレスに認証メールを送信しました。")
                return render(
                    request,
                    "registration/verification_sent.html",
                    {"email": new_email, "email_change": True},
                )

            member.pending_email = ""
            member.email_change_requested_at = None
            member.email_change_token = None
            update_fields.extend(["pending_email", "email_change_requested_at", "email_change_token"])
            member.save(update_fields=update_fields)
            messages.success(request, "アカウント情報を更新しました。")
            return redirect("restaurants:member_account_edit")
    else:
        form = AccountUpdateForm(initial=initial, user=request.user)

    return render(request, "registration/account_edit.html", {"form": form})


@login_required
def mypage(request):
    member, _ = Member.objects.get_or_create(user=request.user, defaults={"full_name": request.user.first_name})
    reservations = Reservation.objects.filter(user=request.user).select_related("restaurant")[:5]
    favorites = Favorite.objects.filter(user=request.user).select_related("restaurant")[:5]
    return render(
        request,
        "restaurants/mypage.html",
        {"member": member, "reservations": reservations, "favorites": favorites},
    )


@login_required
@require_POST
def withdraw(request):
    request.user.delete()
    messages.success(request, "退会しました。")
    return redirect("restaurants:list")


# ===== 有料会員 =====

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

    if not member.stripe_customer_id:
        customer = stripe.Customer.create(
            email=request.user.email,
            name=member.full_name or request.user.first_name or request.user.email,
            metadata={"user_id": str(request.user.id)},
        )
        member.stripe_customer_id = customer.id
        member.save(update_fields=["stripe_customer_id"])

    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=member.stripe_customer_id,
        line_items=[{"price": settings.STRIPE_PRICE_ID, "quantity": 1}],
        success_url=f"{settings.APP_BASE_URL}{reverse('restaurants:billing_success')}?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{settings.APP_BASE_URL}{reverse('restaurants:upgrade_membership')}",
        metadata={"user_id": str(request.user.id)},
    )
    return redirect(session.url, permanent=False)


@login_required
def billing_success(request):
    session_id = request.GET.get("session_id", "").strip()
    if session_id and settings.STRIPE_SECRET_KEY:
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            if session and session.get("payment_status") in ("paid", "no_payment_required"):
                member, _ = Member.objects.get_or_create(
                    user=request.user,
                    defaults={"full_name": request.user.first_name},
                )
                member.stripe_customer_id = session.get("customer") or member.stripe_customer_id
                member.stripe_subscription_id = session.get("subscription") or member.stripe_subscription_id
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
        except Exception:
            # Webhookが正常に到達していればこのフォールバックが失敗しても問題ない。
            pass

    messages.success(request, "決済が完了しました。反映に数秒かかる場合があります。")
    return render(request, "restaurants/billing_success.html")


@login_required
@require_POST
def create_billing_portal_session(request):
    member, _ = Member.objects.get_or_create(user=request.user)
    if not member.stripe_customer_id:
        messages.error(request, "Stripe顧客情報が見つかりません。")
        return redirect("restaurants:upgrade_membership")

    session = stripe.billing_portal.Session.create(
        customer=member.stripe_customer_id,
        return_url=f"{settings.APP_BASE_URL}{reverse('restaurants:mypage')}",
    )
    return redirect(session.url, permanent=False)


@login_required
@require_POST
def cancel_membership(request):
    member, _ = Member.objects.get_or_create(user=request.user)
    if member.stripe_subscription_id:
        stripe.Subscription.modify(
            member.stripe_subscription_id,
            cancel_at_period_end=True,
        )
        messages.success(request, "サブスク解約を受け付けました。現在の契約期間終了後に解約されます。")
    else:
        member.plan_status = Member.PLAN_FREE
        member.paid_ended_at = timezone.now()
        member.save(update_fields=["plan_status", "paid_ended_at"])
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


@csrf_exempt
@require_POST
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

    if endpoint_secret and (sig_header or not settings.DEBUG):
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
        except ValueError:
            return HttpResponse(status=400)
        except stripe.error.SignatureVerificationError:
            return HttpResponse(status=400)
    else:
        try:
            event = json.loads(payload.decode("utf-8"))
        except Exception:
            return HttpResponse(status=400)

    event_id = event.get("id")
    event_type = event.get("type", "")
    data = event.get("data", {}).get("object", {})

    if not event_id or not event_type:
        return HttpResponse(status=400)

    with transaction.atomic():
        webhook_event, _ = StripeWebhookEvent.objects.select_for_update().get_or_create(
            event_id=event_id,
            defaults={
                "event_type": event_type,
                "status": StripeWebhookEvent.STATUS_PENDING,
            },
        )
        if webhook_event.status == StripeWebhookEvent.STATUS_PROCESSED:
            return HttpResponse(status=200)
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
        return HttpResponse(status=500)

    StripeWebhookEvent.objects.filter(pk=webhook_event.pk).update(
        status=StripeWebhookEvent.STATUS_PROCESSED,
        processed_at=timezone.now(),
        last_error="",
    )
    return HttpResponse(status=200)


# ===== 基本情報 =====

def terms(request):
    setting = SiteSetting.objects.first()
    return render(request, "restaurants/terms.html", {"setting": setting})


# ===== 管理者 =====

@staff_member_required
def admin_dashboard(request):
    now = timezone.now()
    ym = request.GET.get("ym", now.strftime("%Y-%m"))
    try:
        target = datetime.strptime(ym, "%Y-%m")
        start = timezone.make_aware(datetime(target.year, target.month, 1))
        if target.month == 12:
            end = timezone.make_aware(datetime(target.year + 1, 1, 1))
        else:
            end = timezone.make_aware(datetime(target.year, target.month + 1, 1))
    except ValueError:
        start = timezone.make_aware(datetime(now.year, now.month, 1))
        if now.month == 12:
            end = timezone.make_aware(datetime(now.year + 1, 1, 1))
        else:
            end = timezone.make_aware(datetime(now.year, now.month + 1, 1))
        ym = now.strftime("%Y-%m")

    total_members = Member.objects.count()
    paid_members = Member.objects.filter(plan_status=Member.PLAN_PAID).count()
    free_members = total_members - paid_members
    total_reservations = Reservation.objects.count()
    total_restaurants = Restaurant.objects.count()

    monthly_sales = (
        Member.objects.filter(plan_status=Member.PLAN_PAID, paid_started_at__gte=start, paid_started_at__lt=end).count()
        * MONTHLY_FEE
    )

    context = {
        "total_members": total_members,
        "paid_members": paid_members,
        "free_members": free_members,
        "total_reservations": total_reservations,
        "total_restaurants": total_restaurants,
        "monthly_sales": monthly_sales,
        "ym": ym,
    }
    return render(request, "restaurants/admin_dashboard.html", context)


@staff_member_required
def admin_member_list(request):
    q = request.GET.get("q", "").strip()
    plan = request.GET.get("plan", "").strip()

    members = Member.objects.select_related("user").all().order_by("-created_at")
    if q:
        members = members.filter(
            Q(full_name__icontains=q) | Q(user__email__icontains=q) | Q(user__username__icontains=q)
        )
    if plan in (Member.PLAN_FREE, Member.PLAN_PAID):
        members = members.filter(plan_status=plan)

    context = {"members": members, "q": q, "plan": plan}
    return render(request, "restaurants/admin_member_list.html", context)


@staff_member_required
def admin_member_detail(request, pk):
    member = get_object_or_404(Member.objects.select_related("user"), pk=pk)
    reservations = Reservation.objects.filter(user=member.user).select_related("restaurant").order_by("-reserved_at")[:20]
    favorites = Favorite.objects.filter(user=member.user).select_related("restaurant").order_by("-id")[:20]
    reviews = Review.objects.filter(user=member.user).select_related("restaurant").order_by("-created_at")[:20]

    context = {
        "member": member,
        "reservations": reservations,
        "favorites": favorites,
        "reviews": reviews,
    }
    return render(request, "restaurants/admin_member_detail.html", context)


@staff_member_required
def admin_restaurant_list(request):
    q = request.GET.get("q", "").strip()
    restaurants = Restaurant.objects.select_related("category").annotate(review_count=Count("reviews")).order_by("-created_at")
    if q:
        restaurants = restaurants.filter(Q(name__icontains=q) | Q(address__icontains=q) | Q(category__name__icontains=q))

    return render(request, "restaurants/admin_restaurant_list.html", {"restaurants": restaurants, "q": q})


@staff_member_required
def admin_restaurant_detail(request, pk):
    restaurant = get_object_or_404(Restaurant.objects.select_related("category"), pk=pk)
    reviews = restaurant.reviews.select_related("user").order_by("-created_at")
    context = {"restaurant": restaurant, "reviews": reviews}
    return render(request, "restaurants/admin_restaurant_detail.html", context)


@staff_member_required
@require_POST
def admin_review_delete(request, pk):
    review = get_object_or_404(Review, pk=pk)
    restaurant_id = review.restaurant_id
    review.delete()
    messages.success(request, "レビューを削除しました。")
    return redirect("restaurants:admin_restaurant_detail", pk=restaurant_id)


@staff_member_required
def admin_review_list(request):
    q_restaurant = request.GET.get("q_restaurant", "").strip()
    q_user = request.GET.get("q_user", "").strip()
    visibility = request.GET.get("visibility", "").strip()

    reviews = Review.objects.select_related("restaurant", "user").order_by("-created_at")
    if q_restaurant:
        reviews = reviews.filter(restaurant__name__icontains=q_restaurant)
    if q_user:
        reviews = reviews.filter(Q(user__email__icontains=q_user) | Q(user__username__icontains=q_user))
    if visibility == "public":
        reviews = reviews.filter(is_public=True)
    elif visibility == "private":
        reviews = reviews.filter(is_public=False)

    context = {
        "reviews": reviews[:300],
        "q_restaurant": q_restaurant,
        "q_user": q_user,
        "visibility": visibility,
    }
    return render(request, "restaurants/admin_review_list.html", context)


@staff_member_required
@require_POST
def admin_review_visibility_toggle(request, pk):
    review = get_object_or_404(Review, pk=pk)
    review.is_public = not review.is_public
    review.save(update_fields=["is_public"])
    messages.success(
        request,
        "レビューを公開にしました。" if review.is_public else "レビューを非公開にしました。",
    )
    return redirect("restaurants:admin_review_list")


@staff_member_required
def admin_category_list(request):
    q = request.GET.get("q", "").strip()
    categories = Category.objects.all().order_by("name")
    if q:
        categories = categories.filter(name__icontains=q)
    return render(request, "restaurants/admin_category_list.html", {"categories": categories, "q": q})


@staff_member_required
def admin_sales_list(request):
    today = timezone.localdate()
    default_start = today.replace(day=1)
    date_from = request.GET.get("date_from", default_start.isoformat()).strip()
    date_to = request.GET.get("date_to", today.isoformat()).strip()

    members = Member.objects.filter(plan_status=Member.PLAN_PAID, paid_started_at__isnull=False).select_related("user")
    if date_from:
        members = members.filter(paid_started_at__date__gte=date_from)
    if date_to:
        members = members.filter(paid_started_at__date__lte=date_to)

    sales_rows = [
        {
            "paid_at": member.paid_started_at,
            "member_name": member.full_name or member.user.first_name or member.user.email,
            "email": member.user.email,
            "amount": MONTHLY_FEE,
        }
        for member in members.order_by("-paid_started_at")
    ]
    total_amount = MONTHLY_FEE * len(sales_rows)

    context = {
        "sales_rows": sales_rows,
        "date_from": date_from,
        "date_to": date_to,
        "total_amount": total_amount,
    }
    return render(request, "restaurants/admin_sales_list.html", context)
