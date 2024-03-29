# Generated by Django 3.2.15 on 2023-02-10 21:18

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0016_remove_address_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="legaladdress",
            name="state",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="profile",
            name="gender",
            field=models.CharField(
                blank=True,
                choices=[
                    ("m", "Male"),
                    ("f", "Female"),
                    ("o", "Other/Prefer Not to Say"),
                ],
                max_length=128,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="profile",
            name="year_of_birth",
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
