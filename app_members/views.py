from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from app_members.forms import AccountUpdateForm, MemberForm
from app_members.services.account_service import (
    clear_pending_email_change,
    request_email_change_verification,
    update_user_full_name,
)
from restaurants.models import Favorite, Member, Reservation


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

            update_user_full_name(user=request.user, full_name=new_full_name)

            member, _ = Member.objects.get_or_create(user=request.user)
            member.full_name = request.user.first_name
            member.save(update_fields=["full_name"])

            if new_email != current_email:
                request_email_change_verification(
                    request=request,
                    user=request.user,
                    member=member,
                    new_email=new_email,
                )
                messages.info(request, "新しいメールアドレスに認証メールを送信しました。")
                return render(
                    request,
                    "registration/verification_sent.html",
                    {"email": new_email, "email_change": True},
                )

            clear_pending_email_change(member)
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
