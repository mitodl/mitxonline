from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("courses", "0105_backfill_course_b2b_contract_relations"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="courserun",
            name="unique_primary_language_per_group",
        ),
        migrations.RemoveConstraint(
            model_name="courserun",
            name="unique_language_per_group",
        ),
        migrations.AlterField(
            model_name="courserun",
            name="b2b_contracts",
            field=models.ManyToManyField(
                blank=True,
                help_text="B2B contracts this course run is attached to.",
                related_name="course_runs",
                to="b2b.contractpage",
            ),
        ),
    ]
