from datetime import datetime

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from restaurants.constants import MONTHLY_FEE
from restaurants.models import Category, Favorite, Member, Reservation, Restaurant, Review


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
