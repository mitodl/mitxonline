"""Line processing hooks."""

import logging

import pluggy

from courses.models import (
    CourseRun,
    CourseRunEnrollment,
    PaidCourseRun,
    PaidProgram,
    Program,
)
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


def _link_b2b_course_run_contracts(line) -> str | None:
    """If the purchased line was a B2B run, make the resulting enrollment a B2B enrollment"""

    from b2b.api import process_add_org_membership  # noqa: PLC0415

    purchased_run = line.purchased_object
    line_user = line.order.purchaser

    if not isinstance(purchased_run, CourseRun):
        log.debug(
            "_link_b2b_course_run_contracts: Item purchased %s is not a course run, skipping",
            purchased_run,
        )
        return

    enrollment = CourseRunEnrollment.objects.filter(
        run=purchased_run,
        user=line_user,
        enrollment_mode=EDX_ENROLLMENT_VERIFIED_MODE,
    ).first()

    if enrollment is None:
        log.error(
            "_link_b2b_course_run_contracts: Purchaser %s has no verified enrollment for %s in order %s",
            line.order.purchaser,
            purchased_run,
            line.order.reference_number,
        )
        return

    if enrollment.b2b_contract_id != line.b2b_contract_id:
        enrollment.b2b_contract_id = line.b2b_contract_id
        enrollment.save_and_log(None)

    if not line_user.user_b2b_contracts.filter(
        contract_page=purchased_run.b2b_contract
    ).exists():
        process_add_org_membership(
            line_user, purchased_run.b2b_contract.organization, keep_until_seen=True
        )
        line_user.b2b_contracts.add(purchased_run.b2b_contract)
        line_user.save()


def _create_program_enrollment(line) -> str | None:
    """Create a program enrollment for the line, if we need to."""

    from courses.api import (  # noqa: PLC0415
        create_program_enrollments,
        upgrade_audit_run_enrollments_for_program_purchase,
    )

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

    upgrade_audit_run_enrollments_for_program_purchase(
        line.order.purchaser, purchased_program
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

    @hookimpl(specname="process_transaction_line", trylast=True)
    def link_b2b_courserun_enrollment(self, line) -> str | None:
        """Call the internal function"""

        return _link_b2b_course_run_contracts(line)
