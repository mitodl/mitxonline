# Generated by Django 3.2.15 on 2023-02-13 20:23

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0017_update_legal_address_and_profile_add_addl_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserProfile",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_on", models.DateTimeField(auto_now_add=True)),
                ("updated_on", models.DateTimeField(auto_now=True)),
                (
                    "gender",
                    models.CharField(
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
                ("year_of_birth", models.IntegerField(blank=True, null=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="user_profile",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.DeleteModel(
            name="Profile",
        ),
    ]
