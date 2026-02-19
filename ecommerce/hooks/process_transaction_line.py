"""Line processing hooks."""

import logging

import pluggy

from courses.models import CourseRun, PaidCourseRun, PaidProgram, Program
from openedx.api import create_user
from openedx.constants import EDX_ENROLLMENT_VERIFIED_MODE

hookimpl = pluggy.HookimplMarker("mitxonline")
log = logging.getLogger(__name__)


def _create_courserun_enrollment(line) -> str | None:
    """Create a course run enrollment for the line, if we need to."""

    from courses.api import create_run_enrollments  # noqa: PLC0415

    if not line.order.is_fulfilled:
        return None

    purchased_run = line.purchased_object

    if not isinstance(purchased_run, CourseRun):
        log.debug("Item purchased %s is not a course run, skipping", purchased_run)
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

    log.debug("Created course run enrollment for %s", purchased_run)


def _create_program_enrollment(line) -> str | None:
    """Create a program enrollment for the line, if we need to."""

    from courses.api import create_program_enrollments  # noqa: PLC0415

    if not line.order.is_fulfilled:
        return None

    purchased_program = line.purchased_object

    if not isinstance(purchased_program, Program):
        log.debug("Item purchased %s is not a program, skipping", purchased_program)
        return None

    create_program_enrollments(
        line.order.purchaser,
        [purchased_program],
        enrollment_mode=EDX_ENROLLMENT_VERIFIED_MODE,
    )

    PaidProgram.objects.create(
        user=line.order.purchaser, program=purchased_program, order=line.order
    )

    log.debug("Created program enrollment for %s", purchased_program)


class CreateEnrollments:
    """Wrapper class for enrollment creation."""

    @hookimpl(specname="process_transaction_line", trylast=True)
    def create_courserun_enrollment(self, line) -> str | None:
        """Call the internal function (so we can test it)"""

        return _create_courserun_enrollment(line=line)

    @hookimpl(specname="process_transaction_line", trylast=True)
    def create_program_enrollment(self, line) -> str | None:
        """Call the internal function (so we can test it)"""

        return _create_program_enrollment(line=line)
