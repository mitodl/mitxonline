# Generated by Django 3.2.13 on 2022-07-08 18:54

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ecommerce", "0015_add_review_status_to_order"),
    ]

    operations = [
        migrations.AddField(
            model_name="discount",
            name="for_flexible_pricing",
            field=models.BooleanField(default=True),
        ),
    ]
