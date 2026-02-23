from django.contrib import messages
from django.db.models import Avg
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from app_public.forms import ReservationForm
from app_public.services.query_service import build_restaurant_list_context
from app_public.services.reservation_service import create_reservation, send_reservation_complete_email
from restaurants.decorators import paid_member_required
from restaurants.models import Coupon, Favorite, Member, Reservation, Restaurant, Review, SiteSetting, UserCoupon

REVIEW_COMMENT_MAX_LENGTH = 500
REVIEW_SCORE_FIELDS = (
    ("rating_atmosphere", "お店の雰囲気"),
    ("rating_taste", "味"),
    ("rating_price", "値段"),
    ("rating_service", "接客"),
)
def legacy_media_restaurant_image(request, path):
    return redirect(static(f"restaurants/{path}"), permanent=False)


def legacy_media_category_image(request, path):
    return redirect(static(f"restaurants_by_category/{path}"), permanent=False)


@paid_member_required
@require_POST
def review_create(request, pk):
    restaurant = get_object_or_404(Restaurant, pk=pk)

    comment = request.POST.get("comment", "").strip()
    scores = {}
    for field_name, label in REVIEW_SCORE_FIELDS:
        value = request.POST.get(field_name, "").strip()
        if not value.isdigit() or not (1 <= int(value) <= 5):
            messages.error(request, f"{label}は1〜5で入力してください。")
            return redirect("restaurants:detail", pk=pk)
        scores[field_name] = int(value)

    if len(comment) > REVIEW_COMMENT_MAX_LENGTH:
        messages.error(request, f"レビュー本文は{REVIEW_COMMENT_MAX_LENGTH}文字以内で入力してください。")
        return redirect("restaurants:detail", pk=pk)

    review, created = Review.objects.update_or_create(
        user=request.user,
        restaurant=restaurant,
        defaults={**scores, "comment": comment},
    )

    messages.success(request, "レビュー投稿できました！" if created else "レビュー更新できました！")
    return redirect("restaurants:detail", pk=pk)


@paid_member_required
@require_POST
def review_delete(request, pk):
    restaurant = get_object_or_404(Restaurant, pk=pk)

    review = Review.objects.filter(user=request.user, restaurant=restaurant).first()
    if not review:
        messages.info(request, "削除するレビューが見つかりませんでした。")
        return redirect("restaurants:detail", pk=pk)

    review.delete()
    messages.success(request, "レビュー削除できました！")
    return redirect("restaurants:detail", pk=pk)


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
    if next_url and url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)

    return redirect("restaurants:detail", pk=pk)


def restaurant_list(request):
    q = request.GET.get("q", "").strip()
    category_id = request.GET.get("category", "").strip()
    budget = request.GET.get("budget", "").strip()
    sort = request.GET.get("sort", "").strip()
    page_number = request.GET.get("page")
    context = build_restaurant_list_context(
        q=q,
        category_id=category_id,
        budget=budget,
        sort=sort,
        page_number=page_number,
    )
    return render(request, "restaurants/restaurant_list.html", context)


def restaurant_detail(request, pk):
    restaurant = get_object_or_404(
        Restaurant.objects.select_related("category").prefetch_related("reviews", "coupons"),
        pk=pk,
    )

    reviews = restaurant.reviews.filter(is_public=True).order_by("-created_at")
    rating_summary = reviews.aggregate(
        avg_rating=Avg("rating"),
        avg_atmosphere=Avg("rating_atmosphere"),
        avg_taste=Avg("rating_taste"),
        avg_price=Avg("rating_price"),
        avg_service=Avg("rating_service"),
    )
    avg_rating = rating_summary["avg_rating"]

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
        "rating_summary": rating_summary,
        "is_favorite": is_favorite,
        "my_review": my_review,
        "member": member,
        "reservation_form": reservation_form,
        "coupons": coupons,
        "my_coupon_ids": my_coupon_ids,
    }
    return render(request, "restaurants/restaurant_detail.html", context)


@paid_member_required
@require_POST
def reservation_create(request, pk):
    restaurant = get_object_or_404(Restaurant, pk=pk)
    form = ReservationForm(request.POST)

    if not form.is_valid():
        messages.error(request, "予約内容に不備があります。")
        return redirect("restaurants:detail", pk=pk)

    reservation = create_reservation(
        user=request.user,
        restaurant=restaurant,
        cleaned_data=form.cleaned_data,
    )
    send_reservation_complete_email(
        user=request.user,
        restaurant=restaurant,
        reservation=reservation,
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


def terms(request):
    setting = SiteSetting.objects.first()
    return render(request, "restaurants/terms.html", {"setting": setting})
