"""Line processing hooks."""

import pluggy

from courses.api import create_program_enrollments, create_run_enrollments
from courses.models import CourseRun, PaidCourseRun, PaidProgram, Program
from openedx.api import create_user
from openedx.constants import EDX_ENROLLMENT_VERIFIED_MODE

hookimpl = pluggy.HookimplMarker("mitxonline")


@hookimpl(specname="process_transaction_line", trylast=True)
def create_courserun_enrollment(line) -> str | None:
    """Create a course run enrollment for the line, if we need to."""

    if not line.order.is_fulfilled:
        return None

    purchased_run = line.purchased_object

    if not isinstance(purchased_run, CourseRun):
        return None

    # Check for an edX user, and create one if there's not one
    if not line.order.purchaser.edx_username:
        create_user(line.order.purchaser)
        line.order.purchaser.refresh_from_db()

    create_run_enrollments(
        line.order.purchaser,
        [purchased_run],
        mode=EDX_ENROLLMENT_VERIFIED_MODE,
        keep_failed_enrollments=True,
    )

    PaidCourseRun.objects.create(
        user=line.order.purchaser, course_run=purchased_run, order=line.order
    )


@hookimpl(specname="process_transaction_line", trylast=True)
def create_program_enrollment(line) -> str | None:
    """Create a program enrollment for the line, if we need to."""

    if not line.order.is_fulfilled:
        return None

    purchased_program = line.purchased_object

    if not isinstance(purchased_program, Program):
        return None

    create_program_enrollments(
        line.order.purchaser,
        [purchased_program],
        enrollment_mode=EDX_ENROLLMENT_VERIFIED_MODE,
    )

    PaidProgram.objects.create(
        user=line.order.purchaser, program=purchased_program, order=line.order
    )
