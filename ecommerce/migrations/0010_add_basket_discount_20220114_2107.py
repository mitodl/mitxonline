# Generated by Django 3.2.10 on 2022-01-14 21:07

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("ecommerce", "0009_basket_item_quantity_default"),
    ]

    operations = [
        migrations.AddField(
            model_name="discountredemption",
            name="redeemed_order",
            field=models.ForeignKey(
                default=1,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="redeemed_order",
                to="ecommerce.order",
            ),
            preserve_default=False,
        ),
        migrations.CreateModel(
            name="BasketDiscount",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_on", models.DateTimeField(auto_now_add=True)),
                ("updated_on", models.DateTimeField(auto_now=True)),
                ("redemption_date", models.DateTimeField()),
                (
                    "redeemed_basket",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="basketdiscount_basket",
                        to="ecommerce.basket",
                    ),
                ),
                (
                    "redeemed_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="basketdiscount_user",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "redeemed_discount",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="basketdiscount_discount",
                        to="ecommerce.discount",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
    ]
