# Generated by Django 3.2.12 on 2022-04-15 19:57

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        (
            "flexiblepricing",
            "0003_update_exhange_rate_convert_rate_to_decimal_unique_code",
        ),
    ]

    operations = [
        migrations.AlterField(
            model_name="flexibleprice",
            name="status",
            field=models.CharField(
                choices=[
                    ("approved", "approved"),
                    ("auto-approved", "auto-approved"),
                    ("created", "created"),
                    ("pending-manual-approval", "pending-manual-approval"),
                    ("skipped", "skipped"),
                    ("reset", "reset"),
                ],
                default="created",
                max_length=30,
            ),
        ),
    ]
