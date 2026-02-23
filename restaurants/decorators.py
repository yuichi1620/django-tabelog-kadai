from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from restaurants.models import Member


def paid_member_required(view_func):
    @login_required
    def _wrapped(request, *args, **kwargs):
        member, _ = Member.objects.get_or_create(user=request.user)
        if not member.is_paid:
            messages.info(request, "この機能は有料会員限定です。")
            return redirect("restaurants:upgrade_membership")
        return view_func(request, *args, **kwargs)

    return _wrapped

