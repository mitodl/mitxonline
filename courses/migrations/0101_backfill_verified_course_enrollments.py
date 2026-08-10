"""Backfill verified course run enrollments for verified program enrollments."""

from django.contrib.contenttypes.models import ContentType
from django.db import migrations
from django.db.models import Exists, OuterRef, Q
from django.utils.timezone import now as tz_now

from openedx.constants import EDX_ENROLLMENT_AUDIT_MODE, EDX_ENROLLMENT_VERIFIED_MODE


def backfill_verified_course_enrollments(apps, schema_editor):
    """
    For users with a verified program enrollment, upgrade any audit-track
    course run enrollments in that program's courses to verified, wherever the
    course run is actually upgradable (live, upgrade window still open, has a
    verified enrollment mode, and has a product).

    Matches courses required/elective directly under the verified program only
    - same scope as the existing purchase-time upgrade in
    courses.api.upgrade_audit_run_enrollments_for_program_purchase, which this
    backfills for enrollments that predate a program purchase or were
    otherwise missed.

    This only corrects the local enrollment_mode field. It does not call the
    edX enrollment API or send enrollment emails, since those are side effects
    that shouldn't happen as part of a deploy-time migration.
    """
    CourseRun = apps.get_model("courses", "CourseRun")
    CourseRunEnrollment = apps.get_model("courses", "CourseRunEnrollment")
    ProgramEnrollment = apps.get_model("courses", "ProgramEnrollment")
    Product = apps.get_model("ecommerce", "Product")

    now = tz_now()
    courserun_content_type = ContentType.objects.get_for_model(CourseRun)

    has_verified_program_purchase = ProgramEnrollment.objects.filter(
        user_id=OuterRef("user_id"),
        program__all_requirements__course_id=OuterRef("run__course_id"),
        enrollment_mode=EDX_ENROLLMENT_VERIFIED_MODE,
        active=True,
    )

    candidates = (
        CourseRunEnrollment.objects.annotate(
            has_verified_program_purchase=Exists(has_verified_program_purchase)
        )
        .filter(
            has_verified_program_purchase=True,
            enrollment_mode=EDX_ENROLLMENT_AUDIT_MODE,
            active=True,
            run__live=True,
            run__enrollment_modes__mode_slug=EDX_ENROLLMENT_VERIFIED_MODE,
        )
        .filter(
            Q(run__upgrade_deadline__isnull=True) | Q(run__upgrade_deadline__gt=now)
        )
        .distinct()
    )

    candidate_run_ids = set(candidates.values_list("run_id", flat=True))
    if not candidate_run_ids:
        return

    upgradable_run_ids = set(
        Product.objects.filter(
            content_type_id=courserun_content_type.id,
            object_id__in=candidate_run_ids,
            is_active=True,
        ).values_list("object_id", flat=True)
    )
    if not upgradable_run_ids:
        return

    candidate_ids = list(
        candidates.filter(run_id__in=upgradable_run_ids).values_list("id", flat=True)
    )
    if not candidate_ids:
        return

    CourseRunEnrollment.objects.filter(id__in=candidate_ids).update(
        enrollment_mode=EDX_ENROLLMENT_VERIFIED_MODE
    )


class Migration(migrations.Migration):
    dependencies = [
        ("courses", "0100_courserunenrollment_edx_enrollment_retry_count"),
        ("ecommerce", "0043_refund_request_status"),
    ]

    operations = [
        migrations.RunPython(
            backfill_verified_course_enrollments, migrations.RunPython.noop
        ),
    ]
