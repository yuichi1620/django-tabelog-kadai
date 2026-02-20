import re

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Member, Reservation, PaymentMethod


class SignUpForm(UserCreationForm):
    full_name = forms.CharField(label="氏名", max_length=100)
    email = forms.EmailField(label="メールアドレス")
    accept_terms = forms.BooleanField(
        label="利用規約に同意する",
        required=True,
    )

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("full_name", "email", "password1", "password2")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        user_model = get_user_model()
        if user_model.objects.filter(email__iexact=email).exists():
            raise ValidationError("このメールアドレスはすでに登録されています。")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        email = self.cleaned_data["email"].strip().lower()
        user.username = email
        user.email = email
        user.first_name = self.cleaned_data["full_name"].strip()
        user.is_active = False
        if commit:
            user.save()
        return user


class MemberForm(forms.ModelForm):
    class Meta:
        model = Member
        fields = ["full_name", "phone_number", "postal_code", "address"]

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get("phone_number", "").strip()
        if not phone_number:
            return phone_number

        if not re.fullmatch(r"[0-9-]+", phone_number):
            raise ValidationError("電話番号は数字とハイフンのみで入力してください。")

        digits = phone_number.replace("-", "")
        if len(digits) not in (10, 11):
            raise ValidationError("電話番号は10桁または11桁で入力してください。")

        return phone_number

    def clean_postal_code(self):
        postal_code = self.cleaned_data.get("postal_code", "").strip()
        if not postal_code:
            return postal_code

        if not re.fullmatch(r"\d{3}-?\d{4}", postal_code):
            raise ValidationError("郵便番号は123-4567形式で入力してください。")

        return postal_code


class AccountUpdateForm(forms.Form):
    full_name = forms.CharField(label="氏名", max_length=100)
    email = forms.EmailField(label="メールアドレス")

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user")
        super().__init__(*args, **kwargs)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        user_model = get_user_model()
        if user_model.objects.filter(email__iexact=email).exclude(pk=self.user.pk).exists():
            raise ValidationError("このメールアドレスはすでに利用されています。")
        return email

    def save(self):
        self.user.first_name = self.cleaned_data["full_name"].strip()
        email = self.cleaned_data["email"].strip().lower()
        self.user.email = email
        self.user.username = email
        self.user.save(update_fields=["first_name", "email", "username"])
        return self.user


class ReservationForm(forms.ModelForm):
    class Meta:
        model = Reservation
        fields = ["reserved_at", "people_count"]
        widgets = {
            "reserved_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def clean_reserved_at(self):
        reserved_at = self.cleaned_data["reserved_at"]
        if reserved_at <= timezone.now():
            raise ValidationError("現在より後の日時を指定してください。")
        return reserved_at


class PaymentMethodForm(forms.ModelForm):
    class Meta:
        model = PaymentMethod
        fields = ["card_brand", "card_last4", "token"]

    def clean_card_last4(self):
        card_last4 = self.cleaned_data.get("card_last4", "").strip()
        if card_last4 and not re.fullmatch(r"\d{4}", card_last4):
            raise ValidationError("カード下4桁は4桁の数字で入力してください。")
        return card_last4
