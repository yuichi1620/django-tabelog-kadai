from django.conf import settings
from django.db import migrations, models
import django.core.validators


def _clamp_score(value):
    return max(1, min(5, int(value or 3)))


def forwards_seed_reviews(apps, schema_editor):
    Review = apps.get_model("restaurants", "Review")
    Restaurant = apps.get_model("restaurants", "Restaurant")
    user_app_label, user_model_name = settings.AUTH_USER_MODEL.split(".")
    User = apps.get_model(user_app_label, user_model_name)

    # 既存レビューは旧rating値を4項目へ反映し、総合評価を再計算して整合を取る。
    for rv in Review.objects.all().iterator():
        base = _clamp_score(rv.rating)
        rv.rating_atmosphere = base
        rv.rating_taste = base
        rv.rating_price = base
        rv.rating_service = base
        rv.rating = base
        rv.save(
            update_fields=[
                "rating",
                "rating_atmosphere",
                "rating_taste",
                "rating_price",
                "rating_service",
            ]
        )

    restaurant_ids = list(Restaurant.objects.order_by("id").values_list("id", flat=True))
    if not restaurant_ids:
        return

    # 全ユーザーに最低1件レビューがある状態にする（未投稿ユーザーのみ1件作成）。
    for user in User.objects.order_by("id").iterator():
        if Review.objects.filter(user_id=user.id).exists():
            continue

        restaurant_id = restaurant_ids[user.id % len(restaurant_ids)]
        seed = user.id * 31 + restaurant_id * 17
        rating_atmosphere = 1 + (seed % 5)
        rating_taste = 1 + ((seed + 1) % 5)
        rating_price = 1 + ((seed + 2) % 5)
        rating_service = 1 + ((seed + 3) % 5)
        overall = (rating_atmosphere + rating_taste + rating_price + rating_service + 2) // 4

        Review.objects.create(
            user_id=user.id,
            restaurant_id=restaurant_id,
            rating=overall,
            rating_atmosphere=rating_atmosphere,
            rating_taste=rating_taste,
            rating_price=rating_price,
            rating_service=rating_service,
            comment="項目別に見て、全体として満足できる内容でした。",
            is_public=True,
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("restaurants", "0013_review_is_public"),
    ]

    operations = [
        migrations.AddField(
            model_name="review",
            name="rating_atmosphere",
            field=models.PositiveSmallIntegerField(
                default=3,
                validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)],
                verbose_name="雰囲気(1-5)",
            ),
        ),
        migrations.AddField(
            model_name="review",
            name="rating_price",
            field=models.PositiveSmallIntegerField(
                default=3,
                validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)],
                verbose_name="値段(1-5)",
            ),
        ),
        migrations.AddField(
            model_name="review",
            name="rating_service",
            field=models.PositiveSmallIntegerField(
                default=3,
                validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)],
                verbose_name="接客(1-5)",
            ),
        ),
        migrations.AddField(
            model_name="review",
            name="rating_taste",
            field=models.PositiveSmallIntegerField(
                default=3,
                validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)],
                verbose_name="味(1-5)",
            ),
        ),
        migrations.AlterField(
            model_name="review",
            name="rating",
            field=models.PositiveSmallIntegerField(
                validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)],
                verbose_name="総合評価(1-5)",
            ),
        ),
        migrations.RunPython(forwards_seed_reviews, noop_reverse),
    ]
