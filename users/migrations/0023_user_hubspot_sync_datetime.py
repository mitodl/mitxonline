# Generated by Django 3.2.18 on 2023-05-23 10:42

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0022_backfill_userprofile_records"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="hubspot_sync_datetime",
            field=models.DateTimeField(null=True),
        ),
    ]
