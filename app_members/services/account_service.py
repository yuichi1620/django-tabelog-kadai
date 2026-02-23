from app_accounts.services.mail_service import build_email_change_token, send_email_change_verification_email


def update_user_full_name(*, user, full_name):
    user.first_name = full_name.strip()
    user.save(update_fields=["first_name"])


def request_email_change_verification(*, request, user, member, new_email):
    member.pending_email = new_email
    member.issue_email_change_token()
    member.save(update_fields=["pending_email", "email_change_requested_at", "email_change_token"])

    token = build_email_change_token(
        user_id=user.pk,
        new_email=new_email,
        nonce=member.email_change_token,
    )
    send_email_change_verification_email(request, new_email=new_email, token=token)


def clear_pending_email_change(member):
    member.pending_email = ""
    member.email_change_requested_at = None
    member.email_change_token = None
    member.save(update_fields=["pending_email", "email_change_requested_at", "email_change_token"])

