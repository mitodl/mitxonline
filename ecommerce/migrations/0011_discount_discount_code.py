# Generated by Django 3.2.12 on 2022-02-22 19:27

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ecommerce", "0010_add_basket_discount_20220114_2107"),
    ]

    operations = [
        migrations.AddField(
            model_name="discount",
            name="discount_code",
            field=models.CharField(default="Test", max_length=50),
            preserve_default=False,
        ),
    ]
