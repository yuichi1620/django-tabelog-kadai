import csv
from io import TextIOWrapper

from django import forms
from django.http import HttpResponse


class RestaurantCsvImportForm(forms.Form):
    csv_file = forms.FileField(label="CSVファイル")


def parse_int(value, default=0):
    try:
        return int(str(value).strip() or default)
    except (TypeError, ValueError):
        return default


def build_csv_response(filename):
    response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def read_uploaded_csv(file_field):
    file_obj = TextIOWrapper(file_field.file, encoding="utf-8-sig")
    return csv.DictReader(file_obj)
