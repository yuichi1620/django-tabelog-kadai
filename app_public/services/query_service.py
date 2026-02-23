from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Avg, Case, Count, F, IntegerField, Q, When

from restaurants.models import Category, Restaurant


def _ordered_by_pk_ids(ids):
    if not ids:
        return None
    return Case(
        *[When(pk=pk, then=pos) for pos, pk in enumerate(ids)],
        output_field=IntegerField(),
    )


def build_restaurant_list_context(*, q, category_id, budget, sort, page_number):
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
    page_obj = paginator.get_page(page_number)

    categories = cache.get("list_categories_v1")
    if categories is None:
        categories = list(Category.objects.all().order_by("name"))
        cache.set("list_categories_v1", categories, 60 * 30)

    coupon_ids = cache.get("list_coupon_restaurant_ids_v1")
    if coupon_ids is None:
        coupon_ids = list(
            Restaurant.objects.filter(coupons__is_active=True)
            .annotate(
                active_coupon_count=Count("coupons", filter=Q(coupons__is_active=True), distinct=True),
                avg_rating=Avg("reviews__rating", filter=Q(reviews__is_public=True)),
            )
            .order_by("-active_coupon_count", F("avg_rating").desc(nulls_last=True), "-created_at")
            .distinct()
            .values_list("id", flat=True)[:8]
        )
        cache.set("list_coupon_restaurant_ids_v1", coupon_ids, 60)
    coupon_order = _ordered_by_pk_ids(coupon_ids)
    coupon_restaurants = (
        Restaurant.objects.none()
        if not coupon_ids
        else Restaurant.objects.select_related("category")
        .filter(pk__in=coupon_ids)
        .annotate(
            active_coupon_count=Count("coupons", filter=Q(coupons__is_active=True), distinct=True),
            avg_rating=Avg("reviews__rating", filter=Q(reviews__is_public=True)),
            _order=coupon_order,
        )
        .order_by("_order")
    )

    top_ids = cache.get("list_top_rated_restaurant_ids_v1")
    if top_ids is None:
        top_ids = list(
            Restaurant.objects.annotate(
                avg_rating=Avg("reviews__rating", filter=Q(reviews__is_public=True)),
                review_count=Count("reviews", filter=Q(reviews__is_public=True), distinct=True),
            )
            .filter(review_count__gt=0)
            .order_by(F("avg_rating").desc(nulls_last=True), "-review_count", "-created_at")
            .values_list("id", flat=True)[:5]
        )
        cache.set("list_top_rated_restaurant_ids_v1", top_ids, 60)
    top_order = _ordered_by_pk_ids(top_ids)
    top_rated_restaurants = (
        Restaurant.objects.none()
        if not top_ids
        else Restaurant.objects.select_related("category")
        .filter(pk__in=top_ids)
        .annotate(
            avg_rating=Avg("reviews__rating", filter=Q(reviews__is_public=True)),
            review_count=Count("reviews", filter=Q(reviews__is_public=True), distinct=True),
            _order=top_order,
        )
        .order_by("_order")
    )

    new_ids = cache.get("list_new_arrival_restaurant_ids_v1")
    if new_ids is None:
        new_ids = list(Restaurant.objects.order_by("-created_at").values_list("id", flat=True)[:8])
        cache.set("list_new_arrival_restaurant_ids_v1", new_ids, 60)
    new_order = _ordered_by_pk_ids(new_ids)
    new_arrival_restaurants = (
        Restaurant.objects.none()
        if not new_ids
        else Restaurant.objects.select_related("category")
        .filter(pk__in=new_ids)
        .annotate(
            avg_rating=Avg("reviews__rating", filter=Q(reviews__is_public=True)),
            review_count=Count("reviews", filter=Q(reviews__is_public=True), distinct=True),
            _order=new_order,
        )
        .order_by("_order")
    )

    return {
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

