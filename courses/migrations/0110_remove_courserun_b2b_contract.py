from django.db import migrations


def backfill_b2b_contracts(apps, schema_editor):
    """
    Copy any remaining b2b_contract values into b2b_contracts.

    0105 already did this, but the FK kept being written after that, so make
    sure nothing is lost before the column goes away.
    """

    CourseRun = apps.get_model("courses", "CourseRun")
    Through = CourseRun.b2b_contracts.through

    runs = CourseRun.all_objects.filter(b2b_contract__isnull=False).values_list(
        "id", "b2b_contract_id"
    )

    Through.objects.bulk_create(
        [
            Through(courserun_id=run_id, contractpage_id=contract_id)
            for run_id, contract_id in runs
        ],
        ignore_conflicts=True,
    )


def restore_b2b_contract(apps, schema_editor):
    """Put the lowest-ID contract from b2b_contracts back into b2b_contract."""

    CourseRun = apps.get_model("courses", "CourseRun")
    Through = CourseRun.b2b_contracts.through

    for run_id, contract_id in (
        Through.objects.order_by("courserun_id", "contractpage_id")
        .distinct("courserun_id")
        .values_list("courserun_id", "contractpage_id")
    ):
        CourseRun.all_objects.filter(id=run_id).update(b2b_contract_id=contract_id)


class Migration(migrations.Migration):
    dependencies = [
        ("courses", "0109_add_manufacturing_variant"),
    ]

    operations = [
        migrations.RunPython(backfill_b2b_contracts, restore_b2b_contract),
        migrations.RemoveField(
            model_name="courserun",
            name="b2b_contract",
        ),
    ]
