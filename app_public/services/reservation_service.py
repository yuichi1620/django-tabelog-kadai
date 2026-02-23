from django.conf import settings
from django.core.mail import send_mail

from restaurants.models import Reservation


def create_reservation(*, user, restaurant, cleaned_data):
    reservation = Reservation(
        user=user,
        restaurant=restaurant,
        reserved_at=cleaned_data["reserved_at"],
        people_count=cleaned_data["people_count"],
        status=Reservation.STATUS_ACTIVE,
    )
    reservation.save()
    return reservation


def send_reservation_complete_email(*, user, restaurant, reservation):
    send_mail(
        subject="【NAGOYAMESHI】予約完了のお知らせ",
        message=(
            f"{restaurant.name} の予約が完了しました。\n"
            f"日時: {reservation.reserved_at}\n"
            f"人数: {reservation.people_count}名"
        ),
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@example.com"),
        recipient_list=[user.email] if user.email else [],
        fail_silently=True,
    )

