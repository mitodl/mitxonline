# Generated by Django 3.2.13 on 2022-06-24 20:07

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("flexiblepricing", "0015_create_flexible_price_tiers"),
    ]

    operations = [
        migrations.AlterField(
            model_name="flexibleprice",
            name="country_of_residence",
            field=models.TextField(blank=True),
        ),
    ]
