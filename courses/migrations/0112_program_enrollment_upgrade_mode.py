"""
Move program enrollments from the edX "verified" mode to the program-only
"upgrade" mode (hq#14063).

Every verified program enrollment is converted, including those the removed
nightly auto-upgrade created without a purchase behind them, so no learner
loses access here. report_unpurchased_upgraded_program_enrollments lists the
ones with no purchase or B2B contract behind them for review.
"""

from django.db import migrations

VERIFIED_MODE = "verified"
UPGRADE_MODE = "upgrade"


def verified_to_upgrade(apps, schema_editor):
    ProgramEnrollment = apps.get_model("courses", "ProgramEnrollment")
    ProgramEnrollment.objects.filter(enrollment_mode=VERIFIED_MODE).update(
        enrollment_mode=UPGRADE_MODE
    )


def upgrade_to_verified(apps, schema_editor):
    ProgramEnrollment = apps.get_model("courses", "ProgramEnrollment")
    ProgramEnrollment.objects.filter(enrollment_mode=UPGRADE_MODE).update(
        enrollment_mode=VERIFIED_MODE
    )


class Migration(migrations.Migration):
    dependencies = [
        ("courses", "0111_course_run_access_role"),
    ]

    operations = [
        migrations.RunPython(verified_to_upgrade, upgrade_to_verified),
    ]
