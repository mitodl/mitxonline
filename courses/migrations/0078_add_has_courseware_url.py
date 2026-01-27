# Generated migration to add has_courseware_url field and populate it based on courseware_url_path

from django.db import migrations, models


def populate_has_courseware_url(apps, schema_editor):
    """
    Set has_courseware_url=False for any course runs where courseware_url_path is NULL.
    This preserves the existing behavior where NULL courseware_url_path meant no URL.
    """
    CourseRun = apps.get_model("courses", "CourseRun")
    # Mark course runs with NULL courseware_url_path as not having a courseware URL
    CourseRun.objects.filter(courseware_url_path__isnull=True).update(
        has_courseware_url=False
    )


def reverse_populate(apps, schema_editor):
    """Reverse: reset to default"""


class Migration(migrations.Migration):
    dependencies = [
        ("courses", "0077_add_paidprogram_model"),
    ]

    operations = [
        migrations.AddField(
            model_name="courserun",
            name="has_courseware_url",
            field=models.BooleanField(
                default=True,
                help_text="Whether this course run should expose a courseware URL. Set to False for test/placeholder runs.",
            ),
        ),
        migrations.RunPython(populate_has_courseware_url, reverse_populate),
    ]
