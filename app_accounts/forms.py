from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.exceptions import ValidationError


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


class EmailLoginForm(AuthenticationForm):
    username = forms.EmailField(
        label="メールアドレス",
        widget=forms.EmailInput(attrs={"autofocus": True}),
    )

    error_messages = {
        "invalid_login": "メールアドレスまたはパスワードが正しくありません。",
        "inactive": "メール認証が完了していません。認証メール内のリンクを開いてください。",
    }

    def clean_username(self):
        return self.cleaned_data["username"].strip().lower()

    def clean(self):
        username = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")

        if username is not None and password:
            self.user_cache = authenticate(self.request, username=username, password=password)
            if self.user_cache is None:
                user_model = get_user_model()
                inactive_user = user_model.objects.filter(username__iexact=username, is_active=False).first()
                if inactive_user and inactive_user.check_password(password):
                    raise ValidationError(self.error_messages["inactive"], code="inactive")
                raise self.get_invalid_login_error()
            self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data


class ResendVerificationEmailForm(forms.Form):
    email = forms.EmailField(label="メールアドレス")

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()

