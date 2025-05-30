# Generated by Django 4.2.20 on 2025-04-25 02:55

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0029_add_b2b_contract_fk"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="completed_onboarding",
            field=models.BooleanField(
                blank=True,
                default=False,
                help_text="Flags if user has completed filling out required onboarding information",
            ),
        ),
    ]
