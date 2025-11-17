# Generated migration to remove old programs M2M field

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("b2b", "0015_migrate_programs_to_contractprogramitem"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="contractpage",
            name="programs",
        ),
    ]
