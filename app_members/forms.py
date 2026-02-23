import re

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from restaurants.models import Member


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

