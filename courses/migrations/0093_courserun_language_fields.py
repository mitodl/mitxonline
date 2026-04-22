"""Add language and is_primary_language fields to CourseRun."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("courses", "0092_enrollment_mode_non_nullable"),
    ]

    operations = [
        migrations.AddField(
            model_name="courserun",
            name="language",
            field=models.CharField(
                blank=True,
                null=True,
                db_index=True,
                max_length=8,
                help_text=(
                    "ISO 639-1 language code for this run "
                    "(e.g. 'en', 'zh', 'fr'). Leave blank for unspecified."
                ),
            ),
        ),
        migrations.AddField(
            model_name="courserun",
            name="is_primary_language",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Designates this run as the primary-language version for its "
                    "run-tag group. The primary run is used as the canonical run "
                    "when grouping language variants. If no run in a group is "
                    "marked primary, the oldest run by creation date is treated "
                    "as primary."
                ),
            ),
        ),
        migrations.AddConstraint(
            model_name="courserun",
            constraint=models.UniqueConstraint(
                condition=models.Q(language__isnull=False),
                fields=["course", "run_tag", "language"],
                name="unique_courserun_course_runtag_language",
            ),
        ),
    ]
