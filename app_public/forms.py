from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from restaurants.models import Reservation


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

