from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("courses", "0086_backfill_enrollment_modes"),
    ]

    operations = [
        migrations.AddField(
            model_name="program",
            name="display_mode",
            field=models.CharField(
                blank=True,
                null=True,
                max_length=32,
                choices=[("course", "course")],
                help_text=(
                    "Set to 'course' to treat this program as a course in APIs."
                ),
            ),
        ),
    ]
