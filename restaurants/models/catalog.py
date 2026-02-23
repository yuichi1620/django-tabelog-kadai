from django.db import models
from django.templatetags.static import static


class Category(models.Model):
    name = models.CharField("カテゴリ名", max_length=50, unique=True)

    class Meta:
        verbose_name = "カテゴリ"
        verbose_name_plural = "カテゴリ"

    def __str__(self):
        return self.name


class Restaurant(models.Model):
    name = models.CharField("店舗名", max_length=100)
    address = models.CharField("住所", max_length=200)
    phone_number = models.CharField("電話番号", max_length=20, blank=True)
    business_hours = models.CharField("営業時間", max_length=120, blank=True)
    description = models.TextField("説明", blank=True)
    image = models.FileField("店舗画像", upload_to="restaurants/", blank=True)

    budget_min = models.PositiveIntegerField("予算下限", default=0)
    budget_max = models.PositiveIntegerField("予算上限", default=0)

    category = models.ForeignKey(
        "Category",
        on_delete=models.PROTECT,
        related_name="restaurants",
    )

    created_at = models.DateTimeField("登録日", auto_now_add=True)

    class Meta:
        verbose_name = "店舗"
        verbose_name_plural = "店舗"

    def __str__(self):
        return self.name

    @property
    def image_display_url(self):
        if not self.image:
            return ""
        # mediaの実ファイルが存在する場合のみmedia URLを返す。
        if self.image.storage.exists(self.image.name):
            return self.image.url
        # media配信できない環境では、同名パスをstatic側に配置してフォールバックする。
        return static(self.image.name)


class SiteSetting(models.Model):
    company_name = models.CharField("会社名", max_length=100, default="NAGOYAMESHI")
    company_description = models.TextField("会社概要", blank=True)
    terms_of_service = models.TextField("利用規約", blank=True)
    updated_at = models.DateTimeField("更新日", auto_now=True)

    class Meta:
        verbose_name = "基本情報設定"
        verbose_name_plural = "基本情報設定"

    def __str__(self):
        return self.company_name

