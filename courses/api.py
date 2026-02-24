"""API for the Courses app"""

from __future__ import annotations

import logging
import re
from collections import namedtuple
from datetime import timedelta
from decimal import Decimal
from traceback import format_exc
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import requests
import reversion
from bs4 import BeautifulSoup
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django_countries import countries
from mitol.common.utils import now_in_utc
from mitol.common.utils.collections import (
    first_or_none,
    has_equal_properties,
)
from mitol.olposthog.features import is_enabled
from opaque_keys.edx.keys import CourseKey
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import HTTPError
from rest_framework.status import HTTP_404_NOT_FOUND

from b2b.api import process_add_org_membership
from cms.api import create_default_courseware_page
from courses import mail_api
from courses.constants import (
    COURSE_KEY_PATTERN,
    ENROLL_CHANGE_STATUS_DEFERRED,
    ENROLL_CHANGE_STATUS_UNENROLLED,
    PROGRAM_TEXT_ID_PREFIX,
)
from courses.models import (
    BaseCertificate,
    BlockedCountry,
    Course,
    CourseRun,
    CourseRunCertificate,
    CourseRunEnrollment,
    CourseRunGrade,
    Department,
    EnrollmentMode,
    PaidCourseRun,
    Program,
    ProgramCertificate,
    ProgramEnrollment,
    ProgramRequirement,
    VerifiableCredential,
)
from courses.serializers.base import get_thumbnail_url
from courses.tasks import subscribe_edx_course_emails
from courses.utils import (
    exception_logging_generator,
    get_enrollable_courseruns_qs,
    is_grade_valid,
    is_letter_grade_valid,
)
from ecommerce.models import OrderStatus, Product
from main import features
from openedx.api import (
    create_edx_course_mode,
    enroll_in_edx_course_runs,
    get_edx_api_course_detail_client,
    get_edx_api_course_list_client,
    get_edx_course_modes,
    get_edx_grades_with_users,
    unenroll_edx_course_run,
)
from openedx.constants import (
    EDX_DEFAULT_ENROLLMENT_MODE,
    EDX_ENROLLMENT_AUDIT_MODE,
    EDX_ENROLLMENT_VERIFIED_MODE,
)
from openedx.exceptions import (
    EdxApiEnrollErrorException,
    NoEdxApiAuthError,
    OpenEdxUserMissingError,
    UnknownEdxApiEnrollException,
)

if TYPE_CHECKING:
    from django.db.models.query import QuerySet
    from edx_api.course_detail.models import CourseMode


log = logging.getLogger(__name__)
UserEnrollments = namedtuple(  # noqa: PYI024
    "UserEnrollments",
    [
        "programs",
        "past_programs",
        "program_runs",
        "non_program_runs",
        "past_non_program_runs",
    ],
)


class InvalidCertificateError(Exception):
    def __init__(self):
        super().__init__("Invalid input for verifiable credential generation.")


def get_relevant_course_run_qset(
    course: Course,
) -> QuerySet:
    """
    Returns a QuerySet of relevant course runs
    """
    enrollable_run_qset = get_enrollable_courseruns_qs(valid_courses=[course])
    return enrollable_run_qset.order_by("enrollment_start")


def get_user_relevant_program_course_run_qset(
    program: Program,
) -> QuerySet:
    """
    Returns a QuerySet of relevant course runs
    """
    enrollable_run_qset = get_enrollable_courseruns_qs(
        valid_courses=program.courses_qset.all()
    )
    return enrollable_run_qset.order_by("enrollment_start")


def create_run_enrollments(  # noqa: C901
    user,
    runs,
    *,
    change_status=None,
    keep_failed_enrollments=None,
    mode=EDX_DEFAULT_ENROLLMENT_MODE,
):
    """
    Creates local records of a user's enrollment in course runs, and attempts to enroll them
    in edX via API.
    Updates the enrollment mode and change_status if the user is already enrolled in the course run
    and now is changing the enrollment mode, (e.g. pays or re-enrolls again or getting deferred)
    Possible cases are:
    1. Downgrade: Verified to Audit via a deferral
    2. Upgrade: Audit to Verified via a payment
    3. Reactivation: Audit to Audit or Verified to Verified via a re-enrollment

    Args:
        user (User): The user to enroll
        runs (iterable of CourseRun): The course runs to enroll in
        change_status (str): The status of the enrollment
        keep_failed_enrollments: (boolean): If True, keeps the local enrollment record
            in the database even if the enrollment fails in edX.
            If None, defaults to the value of the IGNORE_EDX_FAILURES feature flag.
        mode (str): The course mode

    Returns:
        (list of CourseRunEnrollment, bool): A list of enrollment objects that were successfully
            created in mitxonline, paired with a boolean indicating whether or not the edX enrollment API call was successful
            for all of the given course runs
    """
    if keep_failed_enrollments is None:
        keep_failed_enrollments = settings.FEATURES.get(
            features.IGNORE_EDX_FAILURES, False
        )

    successful_enrollments = []

    def send_enrollment_emails():
        subscribe_edx_course_emails.delay(enrollment.id)

    def _enroll_learner_into_associated_programs():
        """
        Enrolls the learner into all programs for which the course they are enrolling into
        is associated as a requirement or elective.  If a program enrollment already exists
        then the change_status of that program_enrollment is checked to ensure it equals None.
        """
        for program in run.course.programs:
            if not program.live:
                continue
            program_enrollment, _ = ProgramEnrollment.objects.get_or_create(
                user=user,
                program=program,
                defaults=dict(  # noqa: C408
                    change_status=None,
                ),
            )
            if program_enrollment.change_status is not None:
                program_enrollment.reactivate_and_save()

    edx_request_success = True
    if not runs[0].is_fake_course_run:
        # Make the API call to enroll the user in edX only if the run is not a fake course run
        try:
            enroll_in_edx_course_runs(
                user,
                runs,
                mode=mode,
            )
        except (
            UnknownEdxApiEnrollException,
            NoEdxApiAuthError,
            OpenEdxUserMissingError,
            RequestsConnectionError,
            EdxApiEnrollErrorException,
            HTTPError,
        ):
            log.exception(
                "edX enrollment failure for user: %s, runs: %s",
                user,
                [run.courseware_id for run in runs],
            )
            edx_request_success = False
            if not keep_failed_enrollments:
                return successful_enrollments, edx_request_success

    is_enrollment_downgraded = False
    for run in runs:
        try:
            enrollment, created = CourseRunEnrollment.all_objects.get_or_create(
                user=user,
                run=run,
                defaults=dict(  # noqa: C408
                    change_status=change_status,
                    edx_enrolled=edx_request_success,
                    enrollment_mode=mode,
                ),
            )

            _enroll_learner_into_associated_programs()

            # If the run is associated with a B2B contract, add the contract
            # to the user's contract list and update their org memberships
            if run.b2b_contract:
                process_add_org_membership(
                    user, run.b2b_contract.organization, keep_until_seen=True
                )
                user.b2b_contracts.add(run.b2b_contract)
                user.save()

            if not created:
                enrollment_mode_changed = mode != enrollment.enrollment_mode
                enrollment.edx_enrolled = edx_request_success
                # This resets the change_status if the enrollment was reactivated or Upgraded/Downgraded
                enrollment.change_status = change_status
                enrollment.save_and_log(None)
                # Case (Upgrade): When user was enrolled in free mode and now enrolls in paid mode (e.g. Verified)
                # Case (Downgrade): When user was enrolled in paid mode and downgrades to a free mode in case
                # of deferral(e.g. Audit)
                # So, User has an active enrollment and the only changing thing is going to be enrollment mode
                if enrollment.active and enrollment_mode_changed:
                    if (
                        mode == EDX_ENROLLMENT_AUDIT_MODE
                        and enrollment.enrollment_mode == EDX_ENROLLMENT_VERIFIED_MODE
                    ):
                        # Downgrade the enrollment
                        is_enrollment_downgraded = True
                    enrollment.update_mode_and_save(mode=mode)

                elif not enrollment.active:
                    if enrollment_mode_changed:
                        enrollment.enrollment_mode = mode
                    enrollment.reactivate_and_save()
                    transaction.on_commit(send_enrollment_emails)
        except:  # pylint: disable=bare-except  # noqa: PERF203, E722
            mail_api.send_enrollment_failure_message(user, run, details=format_exc())
            log.exception(
                "Failed to create/update enrollment record (user: %s, run: %s)",
                user,
                run.courseware_id,
            )
        else:
            successful_enrollments.append(enrollment)
            if enrollment.edx_enrolled and not is_enrollment_downgraded:
                # Do not send enrollment email if the user was downgraded.
                mail_api.send_course_run_enrollment_email(enrollment)
    return successful_enrollments, edx_request_success


def create_program_enrollments(user, programs):
    """
    Creates local records of a user's enrollment in programs

    Args:
        user (User): The user to enroll
        programs (iterable of Program): The course runs to enroll in

    Returns:
        list of ProgramEnrollment: A list of enrollment objects that were successfully created
    """
    successful_enrollments = []
    for program in programs:
        try:
            enrollment, created = ProgramEnrollment.all_objects.get_or_create(
                user=user,
                program=program,
            )
            if not created and not enrollment.active:
                enrollment.reactivate_and_save()
        except:  # pylint: disable=bare-except  # noqa: PERF203, E722
            mail_api.send_enrollment_failure_message(
                user, program, details=format_exc()
            )
            log.exception(
                "Failed to create/update enrollment record (user: %s, program: %s)",
                user,
                program.readable_id,
            )
        else:
            successful_enrollments.append(enrollment)
    return successful_enrollments


def downgrade_learner(enrollment):
    """
    Downgrades given enrollment from verified to audit.
    """

    # Forcing the enrollment here - if the refund comes after the end date
    # for the course for whatever reason, we still want to revert the mode.
    return create_run_enrollments(
        user=enrollment.user,
        runs=[enrollment.run],
        keep_failed_enrollments=True,
        mode=EDX_ENROLLMENT_AUDIT_MODE,
    )


def deactivate_run_enrollment(
    run_enrollment,
    change_status,
    keep_failed_enrollments=None,
):
    """
    Helper method to deactivate a CourseRunEnrollment

    Args:
        run_enrollment (CourseRunEnrollment): The course run enrollment to deactivate
        change_status (str): The change status to set on the enrollment when deactivating
        keep_failed_enrollments: (boolean): If True, keeps the local enrollment record
            in the database even if the enrollment fails in edX.
            If None, defaults to the value of the IGNORE_EDX_FAILURES feature flag.

    Returns:
        CourseRunEnrollment: The deactivated enrollment
    """
    from ecommerce.models import Line  # noqa: PLC0415
    from hubspot_sync.task_helpers import sync_hubspot_line_by_line_id  # noqa: PLC0415

    if keep_failed_enrollments is None:
        keep_failed_enrollments = settings.FEATURES.get(
            features.IGNORE_EDX_FAILURES, False
        )

    try:
        unenroll_edx_course_run(run_enrollment)
    except Exception:  # pylint: disable=broad-except
        log.exception(
            "Failed to unenroll course run '%s' for user '%s' in edX",
            run_enrollment.run.courseware_id,
            run_enrollment.user.email,
        )
        if not keep_failed_enrollments:
            return None
        edx_unenrolled = False
    else:
        edx_unenrolled = True
        mail_api.send_course_run_unenrollment_email(run_enrollment)
    if edx_unenrolled:
        run_enrollment.edx_enrolled = False
        run_enrollment.edx_emails_subscription = False
    run_enrollment.deactivate_and_save(change_status, no_user=True)

    PaidCourseRun.objects.filter(
        user=run_enrollment.user, course_run=run_enrollment.run
    ).delete()

    # Find an associated Line and update HubSpot.
    content_type = ContentType.objects.get(app_label="courses", model="courserun")
    line = Line.objects.filter(
        purchased_object_id=run_enrollment.run.id,
        purchased_content_type=content_type,
        order__state__in=[OrderStatus.FULFILLED, OrderStatus.PENDING],
        order__purchaser=run_enrollment.user,
    )
    if line:
        line_id = line.first().id
        sync_hubspot_line_by_line_id(line_id)
    return run_enrollment


def defer_enrollment(  # noqa: C901
    user,
    from_courseware_id,
    to_courseware_id,
    keep_failed_enrollments=False,  # noqa: FBT002
    force=False,  # noqa: FBT002
):
    """
    Deactivates a user's existing enrollment in one course run and enrolls the user in another.
    If the to_courseware_id is None, the user is simply unenrolled from the from_courseware_id run.

    Args:
        user (User): The enrolled user
        from_courseware_id (str): The courseware_id value of the currently enrolled CourseRun
        to_courseware_id (str): The courseware_id value of the desired CourseRun
        keep_failed_enrollments: (boolean): If True, keeps the local enrollment record
            in the database even if the enrollment fails in edX.
        force (bool): If True, the deferral will be completed even if the current enrollment is inactive
            or the desired enrollment is in a different course

    Returns:
        (CourseRunEnrollment, CourseRunEnrollment): The deactivated enrollment paired with the
            new enrollment that was the target of the deferral
    """
    from_enrollment = CourseRunEnrollment.all_objects.get(
        user=user, run__courseware_id=from_courseware_id
    )

    to_run = (
        CourseRun.objects.get(courseware_id=to_courseware_id)
        if to_courseware_id
        else None
    )

    if to_run is None:
        deferred_enrollments, _ = create_run_enrollments(
            user=user,
            runs=[from_enrollment.run],
            change_status=ENROLL_CHANGE_STATUS_DEFERRED,
            keep_failed_enrollments=keep_failed_enrollments,
            mode=EDX_ENROLLMENT_AUDIT_MODE,
        )
        return first_or_none(deferred_enrollments), None

    downgraded_enrollments = []
    already_deferred_from = (
        from_enrollment.change_status == ENROLL_CHANGE_STATUS_DEFERRED
    )

    if not force and not from_enrollment.active:
        raise ValidationError(
            f"Cannot defer from inactive enrollment (id: {from_enrollment.id}, run: {from_enrollment.run.courseware_id}, user: {user.email}). "  # noqa: EM102
            "Set force=True to defer anyway."
        )
    if from_enrollment.run == to_run:
        raise ValidationError(
            f"Cannot defer to the same course run (run: {to_run.courseware_id})"  # noqa: EM102
        )
    if not force and not to_run.is_enrollable:
        raise ValidationError(
            f"Cannot defer to a course run that is outside of its enrollment period (run: {to_run.courseware_id})."  # noqa: EM102
        )
    if not force and from_enrollment.run.course != to_run.course:
        raise ValidationError(
            f"Cannot defer to a course run of a different course ('{from_enrollment.run.course.title}' -> '{to_run.course.title}'). "  # noqa: EM102
            "Set force=True to defer anyway."
        )

    if already_deferred_from:
        # check if user was already enrolled in verified track
        to_enrollments = CourseRunEnrollment.objects.filter(
            user=user, run=to_run, enrollment_mode=EDX_ENROLLMENT_VERIFIED_MODE
        ).first()
        if to_enrollments:
            return from_enrollment, to_enrollments

    # Deactivate an existing audit enrollment before enrolling in verified
    # this way we enroll in verified even if the upgrade deadline is in the past
    to_enrollments = CourseRunEnrollment.objects.filter(
        user=user, run=to_run, enrollment_mode=EDX_ENROLLMENT_AUDIT_MODE
    ).first()
    if to_enrollments:
        to_enrollments = deactivate_run_enrollment(
            to_enrollments,
            change_status=ENROLL_CHANGE_STATUS_UNENROLLED,
            keep_failed_enrollments=keep_failed_enrollments,
        )
        if to_enrollments is None or to_enrollments.edx_enrolled is True:
            raise Exception(  # noqa: TRY002
                f"Failed to deactivate audit enrollment for course run '{to_run}'"  # noqa: EM102
            )

    to_enrollments, enroll_success = create_run_enrollments(
        user=user,
        runs=[to_run],
        change_status=None,
        keep_failed_enrollments=keep_failed_enrollments,
        mode=EDX_ENROLLMENT_VERIFIED_MODE,
    )
    if not enroll_success and not keep_failed_enrollments:
        raise Exception(  # noqa: TRY002
            f"Api call to enroll on edX was not successful for course run '{to_run}'"  # noqa: EM102
        )
    if not already_deferred_from:
        downgraded_enrollments, enroll_success = create_run_enrollments(
            user=user,
            runs=[from_enrollment.run],
            change_status=ENROLL_CHANGE_STATUS_DEFERRED,
            keep_failed_enrollments=keep_failed_enrollments,
            mode=EDX_ENROLLMENT_AUDIT_MODE,
        )
        if not enroll_success and not keep_failed_enrollments:
            raise Exception(  # noqa: TRY002
                "Api call to change enrollment mode to audit on edX "  # noqa: EM102
                f"was not successful for course run '{from_courseware_id}'"
            )
    if PaidCourseRun.fulfilled_paid_course_run_exists(user, from_enrollment.run):
        from_enrollment.change_payment_to_run(to_run)

    return first_or_none(downgraded_enrollments), first_or_none(to_enrollments)


def ensure_course_run_grade(user, course_run, edx_grade, should_update=False):  # noqa: FBT002
    """
    Ensure that the local grades repository has the grade for the User/CourseRun combination supplied.

    Args:
        user (user.models.User): The user for whom the grade is being synced
        course_run (courses.models.CourseRun): The course run for which the grade is created
        edx_grade (edx_api.grades.models.UserCurrentGrade): The OpenEdx grade object
        should_update (bool): Update the local grade record if it exists

    Returns:
        Tuple[ CourseRunGrade, bool, bool ]: A Tuple containing None or CourseRunGrade object,
            A bool representing if the run grade is created, A bool representing if a run grade is updated
    """
    grade_properties = {
        "grade": edx_grade.percent,
        "passed": edx_grade.passed,
        "letter_grade": edx_grade.letter_grade,
    }

    updated = False
    if should_update:
        with transaction.atomic():
            (
                run_grade,
                created,
            ) = CourseRunGrade.objects.select_for_update().get_or_create(
                course_run=course_run, user=user, defaults=grade_properties
            )

            if (
                not created
                and not run_grade.set_by_admin
                and not has_equal_properties(run_grade, grade_properties)
            ):
                # Perform actual update now.
                run_grade.grade = edx_grade.percent
                run_grade.passed = edx_grade.passed
                run_grade.letter_grade = edx_grade.letter_grade
                run_grade.save_and_log(None)
                updated = True

    else:
        run_grade, created = CourseRunGrade.objects.get_or_create(
            course_run=course_run, user=user, defaults=grade_properties
        )
    return run_grade, created, updated


def _filter_valid_course_keys(runs):
    """Filter runs to get valid course keys and create lookup dict."""
    runs_by_course_id = {}
    invalid_course_ids = []

    for run in runs:
        if re.match(COURSE_KEY_PATTERN, run.courseware_id):
            runs_by_course_id[run.courseware_id] = run
        else:
            invalid_course_ids.append(run.courseware_id)

    if invalid_course_ids:
        log.warning("Skipping invalid course keys: %s", invalid_course_ids)

    valid_course_keys = list(runs_by_course_id.keys())
    return valid_course_keys, runs_by_course_id


def sync_course_runs(runs):
    """
    Sync course run dates and title from Open edX using course list API

    Args:
        runs ([CourseRun]): list of CourseRun objects.

    Returns:
        tuple: (success_count, failure_count) - counts of successful and failed syncs
    """
    api_client = get_edx_api_course_list_client()

    success_count = 0
    failure_count = 0

    valid_course_ids, runs_by_course_id = _filter_valid_course_keys(runs)

    if not valid_course_ids:
        log.warning("No valid course keys found to sync")
        return 0, len(runs)

    try:
        received_course_ids = set()
        for course_detail in api_client.get_courses(
            course_keys=valid_course_ids,
            username=settings.OPENEDX_SERVICE_WORKER_USERNAME,
        ):
            received_course_ids.add(course_detail.course_id)

            if course_detail.course_id not in runs_by_course_id:
                log.warning(
                    "Course detail received for unrequested course ID: %s",
                    course_detail.course_id,
                )
                continue

            run = runs_by_course_id[course_detail.course_id]

            try:
                # Reset the expiration_date so it is calculated automatically and
                # does not raise a validation error now that the start or end date
                # has changed.
                if (
                    run.start_date != course_detail.start
                    or run.end_date != course_detail.end
                ):
                    run.expiration_date = None

                run.title = course_detail.name
                run.start_date = course_detail.start
                run.end_date = course_detail.end
                run.enrollment_start = course_detail.enrollment_start
                run.enrollment_end = course_detail.enrollment_end
                run.is_self_paced = course_detail.is_self_paced()
                # Only sync the date if it's set in edX, Otherwise set it to course's end date
                if course_detail.certificate_available_date:
                    run.certificate_available_date = (
                        course_detail.certificate_available_date
                    )
                else:
                    run.certificate_available_date = course_detail.end

                run.save()
                success_count += 1
                log.info("Updated course run: %s", run.courseware_id)

            except Exception as e:  # pylint: disable=broad-except  # noqa: BLE001
                # Report any validation or otherwise model errors
                log.error("%s: %s", str(e), run.courseware_id)  # noqa: TRY400
                failure_count += 1

        missing_course_ids = set(valid_course_ids) - received_course_ids
        if missing_course_ids:
            log.warning(
                "No data received for requested courses: %s",
                list(missing_course_ids),
            )

    except HTTPError as e:
        failure_count += 1
        log.error("Bulk course list API error: %s", str(e))  # noqa: TRY400
    except Exception as e:  # pylint: disable=broad-except  # noqa: BLE001
        failure_count += 1
        log.error("Unexpected error in bulk sync: %s", str(e))  # noqa: TRY400

    return success_count, failure_count


def pull_course_modes(run: CourseRun) -> tuple[list[CourseMode], int]:
    """
    Pull the course modes for the given run and store them locally.

    We only generally care about "audit" and "verified", but this will store any
    others that happen to be configured as well.

    Args:
        run (CourseRun): CourseRun object to retrieve modes for
    Returns:
        tuple of edX modes retrieved and count of modes created
    """

    modes = get_edx_course_modes(course_id=run.courseware_id)
    new_mode_count = 0

    for edx_mode in modes:
        mxo_mode, created = EnrollmentMode.objects.get_or_create(
            mode_slug=edx_mode.mode_slug,
            defaults={
                "mode_display_name": edx_mode.mode_display_name,
                "requires_payment": edx_mode.mode_slug == EDX_ENROLLMENT_VERIFIED_MODE,
            },
        )

        run.enrollment_modes.add(mxo_mode)

        if created:
            new_mode_count += 1

    run.save()

    return (modes, new_mode_count)


def check_course_modes(run: CourseRun) -> tuple[bool, bool]:
    """
    Check that the course has the course modes we expect.

    We expect an `audit` and a `verified` mode in our course runs. If these don't
    exist for the given course, this will create them on both the edX side and
    on the MITx Online side. (If the default audit and verified modes don't exist,
    then we'll make those too.)

    Args:
        runs (CourseRun): CourseRun object to check

    Returns:
        (audit_created: bool, verified_created: bool): Tuple of mode status - true for created, false for found
    """

    modes, _ = pull_course_modes(run)

    found_audit, found_verified = (False, False)

    mxo_audit_mode, _ = EnrollmentMode.objects.get_or_create(
        mode_slug=EDX_ENROLLMENT_AUDIT_MODE,
        defaults={
            "mode_display_name": EDX_ENROLLMENT_AUDIT_MODE,
            "requires_payment": False,
        },
    )
    mxo_verified_mode, _ = EnrollmentMode.objects.get_or_create(
        mode_slug=EDX_ENROLLMENT_VERIFIED_MODE,
        defaults={
            "mode_display_name": EDX_ENROLLMENT_VERIFIED_MODE,
            "requires_payment": True,
        },
    )

    for mode in modes:
        if mode.mode_slug == EDX_ENROLLMENT_AUDIT_MODE:
            found_audit = True

        if mode.mode_slug == EDX_ENROLLMENT_VERIFIED_MODE:
            found_verified = True

    if not found_audit:
        create_edx_course_mode(
            course_id=run.courseware_id,
            mode_slug=EDX_ENROLLMENT_AUDIT_MODE,
            mode_display_name="Audit",
            description="Audit",
            expiration_datetime=None,
            currency="USD",
        )
        run.enrollment_modes.add(mxo_audit_mode)

    if not found_verified:
        create_edx_course_mode(
            course_id=run.courseware_id,
            mode_slug=EDX_ENROLLMENT_VERIFIED_MODE,
            mode_display_name="Verified",
            description="Verified",
            currency="USD",
            min_price=10,
            expiration_datetime=run.upgrade_deadline if run.upgrade_deadline else None,
        )
        run.enrollment_modes.add(mxo_verified_mode)

    if not (found_audit or found_verified):
        run.save()

    # these are created flags, not found flags
    return (not found_audit, not found_verified)


def sync_course_mode(runs: list[CourseRun]) -> list[int]:
    """
    Sync the course runs' upgrade deadline with the expiration date in its verified mode.

    Args:
        runs ([CourseRun]): list of CourseRun objects.

    Returns:
        [int, int]: Count of successful and failed operations
    """

    success_count = 0
    failure_count = 0

    # Iterate all eligible runs and sync if possible
    for run in runs:
        try:
            course_modes, _ = pull_course_modes(run)
        except HTTPError as e:  # noqa: PERF203
            failure_count += 1
            if e.response.status_code == HTTP_404_NOT_FOUND:
                log.error(  # noqa: TRY400
                    "Course mode not found on edX for readable id: %s",
                    run.courseware_id,
                )
            else:
                log.error("%s: %s", str(e), run.courseware_id)  # noqa: TRY400
        except Exception as e:  # pylint: disable=broad-except  # noqa: BLE001
            failure_count += 1
            log.error("%s: %s", str(e), run.courseware_id)  # noqa: TRY400
        else:
            for course_mode in course_modes:
                if (
                    course_mode.mode_slug == EDX_ENROLLMENT_VERIFIED_MODE
                    and run.upgrade_deadline != course_mode.expiration_datetime
                ):
                    run.upgrade_deadline = course_mode.expiration_datetime
                    try:
                        run.save()
                        success_count += 1
                        log.info(
                            "Updated upgrade deadline for course run: %s",
                            run.courseware_id,
                        )
                    except Exception as e:  # pylint: disable=broad-except  # noqa: BLE001
                        # Report any validation or otherwise model errors
                        log.error("%s: %s", str(e), run.courseware_id)  # noqa: TRY400
                        failure_count += 1

    return [success_count, failure_count]


def is_program_text_id(item_text_id):
    """
    Analyzes a text id for some enrollable item and returns True if it's a program id

    Args:
        item_text_id (str): The text id for some enrollable item (program/course run)

    Returns:
        bool: True if the given id is a program id
    """
    return item_text_id.startswith(PROGRAM_TEXT_ID_PREFIX)


def process_course_run_grade_certificate(course_run_grade, should_force_create=False):  # noqa: FBT002
    """
    Ensure that the course run certificate is in line with the values in the course run grade

    Args:
        course_run_grade (courses.models.CourseRunGrade): The course run grade for which to generate/delete the certificate
        should_force_create (bool): If True, it will force the certificate creation without matching criteria
    Returns:
        Tuple[ CourseRunCertificate, bool, bool ]: A Tuple containing None or CourseRunCertificate object,
            A bool representing if the certificate is created, A bool representing if a certificate is deleted
    """
    from hubspot_sync.task_helpers import sync_hubspot_user  # noqa: PLC0415

    user = course_run_grade.user
    course_run = course_run_grade.course_run

    # A grade of 0.0 indicates that the certificate should be deleted
    should_delete = not bool(course_run_grade.grade)
    should_create = course_run_grade.is_certificate_eligible or should_force_create

    if should_delete:
        delete_count, _ = CourseRunCertificate.objects.filter(
            user=user, course_run=course_run
        ).delete()
        sync_hubspot_user(user)
        return None, False, (delete_count > 0)

    elif should_create:
        try:
            certificate, created = CourseRunCertificate.objects.get_or_create(
                user=user, course_run=course_run
            )
            sync_hubspot_user(user)
            if not certificate.verifiable_credential_id:
                create_verifiable_credential(certificate)
            return certificate, created, False  # noqa: TRY300
        except IntegrityError:
            log.warning(
                f"IntegrityError caught processing certificate for {course_run.courseware_id} for user {user} - certificate was likely already revoked."  # noqa: G004
            )
    return None, False, False


def get_certificate_grade_eligible_runs(now):
    """
    Get the list of course runs that are eligible for Grades update/creation and certificates creation
    """
    # Get all the course runs eligible for certificates generation
    # For a valid run it would be live, certificate_available_date would be in future or within a month of passing
    # the certificate_available_date.

    course_runs = CourseRun.objects.live(include_b2b=True).filter(
        Q(certificate_available_date__isnull=True)
        | Q(
            certificate_available_date__gt=now
            - timedelta(days=settings.CERTIFICATE_CREATION_WINDOW_IN_DAYS)
        )
    )
    return course_runs  # noqa: RET504


def generate_course_run_certificates():
    """
    Hits the edX grades API for eligible course runs and generates the certificates and grades for users for course runs
    """
    now = now_in_utc()
    course_runs = get_certificate_grade_eligible_runs(now)

    if course_runs is None or course_runs.count() == 0:
        log.info("No course runs matched the certificates generation criteria")
        return

    for run in course_runs:
        edx_grade_user_iter = exception_logging_generator(
            get_edx_grades_with_users(run)
        )
        created_grades_count, updated_grades_count, generated_certificates_count = (
            0,
            0,
            0,
        )
        for edx_grade, user in edx_grade_user_iter:
            try:
                course_run_grade, created, updated = ensure_course_run_grade(
                    user=user, course_run=run, edx_grade=edx_grade, should_update=True
                )
            except ValidationError:
                msg = f"Can't save grade {edx_grade} for {user} in {run}, skipping certificate generation"
                log.exception(msg)
                continue

            if created:
                created_grades_count += 1
            elif updated:
                updated_grades_count += 1

            # Check certificate generation eligibility
            #   1. For self_paced course runs we generate certificates right away irrespective
            #   of certificate_available_date
            #   2. For others course runs we generate the certificates if the certificate_available_date of course run
            #   has passed
            if run.is_self_paced or (
                run.certificate_available_date and run.certificate_available_date <= now
            ):
                _, created, deleted = process_course_run_grade_certificate(
                    course_run_grade=course_run_grade
                )

                if deleted:
                    log.warning(
                        "Certificate deleted for user %s and course_run %s", user, run
                    )
                elif created:
                    log.warning(
                        "Certificate created for user %s and course_run %s", user, run
                    )
                    generated_certificates_count += 1
        log.info(
            f"Finished processing course run {run}: created grades for {created_grades_count} users, updated grades for {updated_grades_count} users, generated certificates for {generated_certificates_count} users"  # noqa: G004
        )


def manage_course_run_certificate_access(user, courseware_id, revoke_state):
    """
    Revokes/Un-Revokes a course run certificate.

    Args:
        user (User): a Django user.
        courseware_id (str): A string representing the course run's courseware_id.
        revoke_state (bool): A flag representing True(Revoke), False(Un-Revoke)

    Returns:
        bool: A boolean representing the revoke/unrevoke success
    """
    course_run = CourseRun.objects.get(courseware_id=courseware_id)

    try:
        course_run_certificate = CourseRunCertificate.all_objects.get(
            user=user, course_run=course_run
        )
    except CourseRunCertificate.DoesNotExist:
        log.warning(
            "Course run certificate for user: %s and course_run: %s does not exist.",
            user.edx_username,
            course_run,
        )
        return False

    course_run_certificate.is_revoked = revoke_state
    course_run_certificate.save()

    return True


def override_user_grade(
    user,
    override_grade,
    letter_grade,
    courseware_id,
    should_force_pass=False,  # noqa: FBT002
):
    """Override grade for a user

    Args:
        user (User): a Django user.
        courseware_id (str): A string representing the course run's courseware_id.
        override_grade (float): A float value for the grade override between (0.0 and 1.0) - 0.0 would mean passed=False
        letter_grade (str): A string representing a letter grade for the course run.
        should_force_pass (bool): A flag representing if user should mark as passed forcefully (In this case we don't know
        the grading policy based in edX so we manually take a value for forcing the passed status)
    Returns:
        (CourseRunGrade): The updates grade of the user
    """

    if not is_grade_valid(override_grade):
        raise ValidationError("Invalid value for grade. Allowed range: 0.0 - 1.0")  # noqa: EM101

    if not is_letter_grade_valid(letter_grade):
        raise ValidationError("Invalid letter grade string. Allowed values: A-F")  # noqa: EM101

    with transaction.atomic():
        course_run_grade = CourseRunGrade.objects.select_for_update().get(
            user=user, course_run__courseware_id=courseware_id
        )
        course_run_grade.grade = override_grade
        course_run_grade.passed = bool(override_grade) if should_force_pass else False
        course_run_grade.letter_grade = letter_grade
        course_run_grade.set_by_admin = True
        course_run_grade.save_and_log(None)

    return course_run_grade


def _has_earned_program_cert(user, program):
    """
    Checks if a user has earned all the course certificates required
    for a given program.

    Args:
        user (User): a Django user.
        program (programs.models.Program): program where the user is enrolled.

    Returns:
        bool: True if a user has earned all the course certificates required
              for a given program else False
    """
    program_course_ids = [course[0].id for course in program.courses]

    passed_courses = Course.objects.filter(
        id__in=program_course_ids,
        courseruns__courseruncertificates__user=user,
        courseruns__courseruncertificates__is_revoked=False,
    )
    root = ProgramRequirement.get_root_nodes().get(program=program)

    def _has_earned(node):
        if node.is_root or node.is_all_of_operator:
            # has passed all of the child requirements
            return all(_has_earned(child) for child in node.get_children())
        elif node.is_min_number_of_operator:
            # has passed a minimum of the child requirements
            return len(list(filter(_has_earned, node.get_children()))) >= int(
                node.operator_value
            )
        elif node.is_course:
            # has passed the reference course
            return node.course in passed_courses
        elif node.is_program:
            # has earned certificate for the required sub-program
            return ProgramCertificate.objects.filter(
                user=user, program=node.required_program, is_revoked=False
            ).exists()
        return False

    return _has_earned(root)


def generate_program_certificate(user, program, force_create=False):  # noqa: FBT002
    """
    Create a program certificate if the user has a course certificate
    for each course in the program. Also, It will create the
    program enrollment if it does not exist for the user.

    Args:
        user (User): a Django user.
        program (programs.models.Program): program where the user is enrolled.
        force_create (bool): Default False, ignores the requirement of passing
                            the courses for the program certificate if True

    Returns:
        (ProgramCertificate or None, bool): A tuple containing a
        ProgramCertificate (or None if one was not found or created) paired
        with a boolean indicating whether the certificate was newly created.
    """
    from hubspot_sync.task_helpers import sync_hubspot_user  # noqa: PLC0415

    existing_cert_queryset = ProgramCertificate.all_objects.filter(
        user=user, program=program
    )
    if existing_cert_queryset.exists():
        ProgramEnrollment.objects.get_or_create(
            program=program, user=user, defaults={"active": True, "change_status": None}
        )
        return existing_cert_queryset.first(), False

    if not force_create and not _has_earned_program_cert(user, program):
        return None, False

    program_cert = ProgramCertificate.objects.create(user=user, program=program)
    if program_cert:
        log.info(
            "Program certificate for [%s] in program [%s] is created.",
            user.edx_username,
            program.title,
        )
        sync_hubspot_user(user)
        if not program_cert.verifiable_credential_id:
            create_verifiable_credential(program_cert)

        _, created = ProgramEnrollment.objects.get_or_create(
            program=program, user=user, defaults={"active": True, "change_status": None}
        )

        if created:
            log.info(
                "Program enrollment for [%s] in program [%s] is created.",
                user.edx_username,
                program.title,
            )

    return program_cert, True


def generate_multiple_programs_certificate(user, programs):
    """
    Create a program certificate if the user has a course certificate
    for each course in the program. Also, It will create the
    program enrollment if it does not exist for the user.

    Args:
        user (User): a Django user.
        programs (list of objects of programs.models.Program): programs where the user is enrolled.

    Returns:
        list of [(ProgramCertificate or None, bool), (ProgramCertificate or None, bool)]: the return
        result is ordered as the order of programs list

    (ProgramCertificate or None, bool): A tuple containing a
    ProgramCertificate (or None if one was not found or created) paired
    with a boolean indicating whether the certificate was newly created.
    """
    results = []
    for program in programs:
        result = generate_program_certificate(user, program)
        results.append(result)
    return results


def manage_program_certificate_access(user, program, revoke_state):
    """
    Revokes/Un-Revokes a program certificate.

    Args:
        user (User): a Django user.
        program (Program): A Program model object.
        revoke_state (bool): A flag representing True(Revoke), False(Un-Revoke)

    Returns:
        bool: A boolean representing the revoke/unrevoke success
    """

    try:
        program_certificate = ProgramCertificate.all_objects.get(
            user=user, program=program
        )
    except ProgramCertificate.DoesNotExist:
        log.warning(
            "Program certificate for user: %s and program: %s does not exist.",
            user.edx_username,
            program.readable_id,
        )
        return False

    program_certificate.is_revoked = revoke_state
    program_certificate.save()

    return True


def resolve_courseware_object_from_id(
    courseware_id: str,
) -> Program | Course | CourseRun | None:
    """
    Resolves a courseware_id to a CourseRun, Course, or Program.

    Args:
        courseware_id (str): The courseware_id to resolve.

    Returns:
        CourseRun | Course | Program | None: The resolved object or None if not found.
    """
    if is_program_text_id(courseware_id):
        return Program.objects.filter(readable_id=courseware_id).first()
    return (
        CourseRun.objects.filter(courseware_id=courseware_id).first()
        or Course.objects.filter(readable_id=courseware_id).first()
    )


def generate_openedx_course_url(course_key: str) -> str:
    """
    Generate a valid edX course URL for the given course key.

    Configuration Settings:
    - OPENEDX_COURSE_BASE_URL: the base URL to use
    - OPENEDX_COURSE_BASE_URL_SUFFIX: optional suffix to append to the URL
    Args:
    - course_key (str): the course key (course-v1:MITxT+1234x+1T2099) to use
    Returns:
    - str, the generated URL
    """

    parsed_base = urlparse(settings.OPENEDX_COURSE_BASE_URL)
    suffix = (
        "/" + settings.OPENEDX_COURSE_BASE_URL_SUFFIX.lstrip().lstrip("/")
        if settings.OPENEDX_COURSE_BASE_URL_SUFFIX
        else ""
    )
    new_path = f"{parsed_base[2]}{course_key}{suffix}"

    return parsed_base._replace(path=new_path).geturl()


def import_courserun_from_edx(  # noqa: C901, PLR0913
    course_key: str,
    *,
    live: bool = False,
    use_specific_course: str | None = None,
    departments: list[Department | str] | None = None,
    create_depts: bool = False,
    block_countries: list[str] | None = None,
    price: Decimal | None = None,
    create_cms_page: bool = False,
    publish_cms_page: bool = False,
    include_in_learn_catalog: bool = False,
    ingest_content_files_for_ai: bool = False,
    is_source_run: bool = False,
):
    """
    Import a course run from edX.

    This checks for the course run in edX, and imports it if it exists. If
    necessary, it creates:
    - The underlying Course object
    - Any necessary Departments (if the flag for this is set)
    - A Product (if a price is set)
    - A CMS page (if the flag is set; will publish if the flag is set)

    It will also add the blocked countries for the course if those are set.

    If the course does need to be created, departments must be supplied. The
    function will throw an AttributeError if there aren't any. An empty list can
    be supplied if the course exists.

    A specific course can be specified. This is to cover cases where the run you
    may want to import doesn't technically "live" under the course that is
    specified in its key. (This happens with B2B/UAI courses - the course will
    be in the UAI_SOURCE org, but the runs all use an org that matches up with
    the contract on the MITx Online side. E.g. course-v1:UAI_SOURCE+UAI.0 is the
    root course for course-v1:UAI_MIT+UAI.0+2025_C999.)

    If the specified course run exists, then this won't do anything. There are
    separate processes to update an existing run from edX data.

    This will not add the course to any programs - you can do that later.

    Args:
    - course_key (str): The readable ID of the course run to import.
    - live (bool): Make the new course run live, and the course if one is created.
    - use_specific_course (str|None): Readable ID of a specific course to use as the base course.
    - departments (list[Department | str] | None): Departments to add to the new course. Only required if creating a new course.
    - create_depts (bool): Create departments.
    - block_countries (list[str] | None): Country codes to add to the block list for the course.
    - price (Decimal | None): Price for the course product, if any. If no price is set, a product won't be created.
    - create_cms_page (bool): Create a CMS page for the course. Only applies if a course is being created.
    - publish_cms_page (bool): Publish the new CMS page. Only takes effect if creating a CMS page.
    - include_in_learn_catalog (bool): Set the "include_in_learn_catalog" flag on the new page.
    - ingest_content_files_for_ai (bool): Set the "ingest_content_files_for_ai" flag on the new page.
    - is_source_run (bool): Set the "is_source_run" flag on the course run to designate it as a B2B source course.
    Returns:
    tuple of (CourseRun, CoursePage|None, Product|None) - relevant objects for the imported run
    """

    if CourseRun.objects.filter(courseware_id=course_key).exists():
        return False

    processed_course_key = CourseKey.from_string(course_key)

    edx_course_detail = get_edx_api_course_detail_client()

    edx_course_run = edx_course_detail.get_detail(
        course_id=course_key,
        username=settings.OPENEDX_SERVICE_WORKER_USERNAME,
    )

    processed_run_key = CourseKey.from_string(edx_course_run.course_id)

    if use_specific_course:
        root_course = Course.objects.get(readable_id=use_specific_course)
    else:
        # edX doesn't have the concept of a "Course", so there's not an opaque
        # key type for it.
        root_course_id = (
            f"course-v1:{processed_course_key.org}+{processed_course_key.course}"
        )
        root_course = Course.objects.filter(readable_id=root_course_id).first()

        if not root_course:
            if not departments or len(departments) == 0:
                msg = f"Course {root_course_id} would be created, so departments are required."
                raise AttributeError(msg)

            root_course = Course.objects.create(
                readable_id=root_course_id,
                title=edx_course_run.name,
                live=live,
            )

            for department in departments:
                if isinstance(department, str) and create_depts:
                    dept, _ = Department.objects.get_or_create(name=department)
                    dept.save()
                elif isinstance(department, Department):
                    dept = department

                root_course.departments.add(dept.id)

    new_run = CourseRun.objects.create(
        course=root_course,
        run_tag=processed_run_key.run,
        courseware_id=edx_course_run.course_id,
        start_date=edx_course_run.start,
        end_date=edx_course_run.end,
        enrollment_start=edx_course_run.enrollment_start,
        enrollment_end=edx_course_run.enrollment_end,
        title=edx_course_run.name,
        live=live,
        is_self_paced=edx_course_run.is_self_paced(),
        is_source_run=is_source_run,
    )

    course_page = None
    if create_cms_page and not use_specific_course:
        course_page = create_default_courseware_page(
            courseware=new_run.course,
            live=publish_cms_page,
            ingest_content_files_for_ai=ingest_content_files_for_ai,
            include_in_learn_catalog=include_in_learn_catalog,
        )

    course_product = None
    if price:
        content_type = ContentType.objects.get_for_model(CourseRun)
        with reversion.create_revision():
            course_product, _ = Product.objects.update_or_create(
                content_type=content_type,
                object_id=new_run.id,
                defaults={
                    "price": Decimal(price),
                    "description": new_run.courseware_id,
                    "is_active": True,
                },
            )

            course_product.save()

    if block_countries:
        for block_country in block_countries:
            country_code = countries.by_name(block_country)
            if not country_code:
                country_name = countries.countries.get(block_country, None)
                country_code = block_country if country_name else None
            else:
                country_name = block_country

            if country_code:
                BlockedCountry.objects.get_or_create(
                    course=new_run.course, country=country_code
                )

    return (new_run, course_page, course_product)


ACHIEVEMENT_TYPE_MAP = {
    "course_run": "Course",
    "program": "Program",
}

# Maps the value of settings.ENVIRONMENT to the hostname for that environment's Learn instance
# This is ugly, if anyone has other suggestions I'm all ears.
ENV_TO_LEARN_HOSTNAME_MAP = {
    "production": "learn.mit.edu",
    "rc": "learn.rc.mit.edu",
    "ci": "learn.ci.mit.edu",
}


def get_verifiable_credentials_payload(certificate: BaseCertificate) -> dict:
    # TODO: We could optimize these queries #noqa: TD002, TD003, FIX002
    # It's not a massive priority though, as we have a total of 20k certs in prod as of 12/25
    learn_hostname = ENV_TO_LEARN_HOSTNAME_MAP.get(
        settings.ENVIRONMENT, "learn.mit.edu"
    )

    if isinstance(certificate, CourseRunCertificate):
        cert_type = "course_run"
        course_run = certificate.course_run
        course = course_run.course
        course_page = course.page
        if not course_page.what_you_learn:
            # If it's empty, we can't generate a valid payload as narrative is required.
            log.error(
                "Error creating verifiable credential - missing 'what_you_learn' for course page %s for certificate %s",
                course_page.title,
                certificate,
            )
            raise InvalidCertificateError

        course_url_id = course.readable_id
        url = f"https://{learn_hostname}/courses/{course_url_id}"
        certificate_name = certificate.course_run.title
        activity_start_date = CourseRunEnrollment.all_objects.get(
            user_id=certificate.user_id, run=course_run
        ).created_on.strftime("%Y-%m-%dT%H:%M:%SZ")
        achievement_image_url = (
            get_thumbnail_url(course_page) if course_page.feature_image else ""
        )
        soup = BeautifulSoup(course_page.what_you_learn, "html.parser")
        narrative = "\n".join(
            [f"- {stripped_string}" for stripped_string in soup.stripped_strings]
        )

    elif isinstance(certificate, ProgramCertificate):
        cert_type = "program"
        program = certificate.program
        program_page = program.page
        url = f"https://{learn_hostname}/programs/{program.readable_id}"
        certificate_name = certificate.program.title
        activity_start_date = ProgramEnrollment.all_objects.get(
            user_id=certificate.user_id, program=program
        ).created_on.strftime("%Y-%m-%dT%H:%M:%SZ")
        achievement_image_url = (
            get_thumbnail_url(program_page) if program_page.feature_image else ""
        )
        narrative = "\n".join(
            [f"- {program_course[0].title}" for program_course in program.courses]
        )
    else:
        raise InvalidCertificateError

    achievement_type = ACHIEVEMENT_TYPE_MAP[cert_type]
    user_name = certificate.user.name
    valid_from = (
        certificate.issue_date.strftime("%Y-%m-%dT%H:%M:%SZ")
        if certificate.issue_date
        else certificate.created_on.strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    activity_end_date = valid_from
    payload = {
        "@context": [
            "https://www.w3.org/ns/credentials/v2",
            "https://purl.imsglobal.org/spec/ob/v3p0/context-3.0.3.json",
            "https://w3id.org/security/suites/ed25519-2020/v1",
        ],
        "id": f"urn:uuid:{certificate.uuid}",
        "type": ["VerifiableCredential", "OpenBadgeCredential"],
        "issuer": {
            "id": f"did:key:{settings.VERIFIABLE_CREDENTIAL_DID}",
            "type": ["Profile"],
            "name": "MIT Learn",
            "image": {
                "id": "https://learn.mit.edu/images/mit-red.png",
                "type": "Image",
                "caption": "MIT Learn logo",
            },
        },
        "validFrom": valid_from,
        "credentialSubject": {
            "type": ["AchievementSubject"],
            "activityStartDate": activity_start_date,
            "activityEndDate": activity_end_date,
            "identifier": [
                {
                    "type": "IdentityObject",
                    "identityHash": user_name,
                    "identityType": "name",
                    "hashed": False,
                    "salt": "not-used",
                }
            ],
            "achievement": {
                # The ID is supposed to be an unambiguous URI corresponding to the course or program.
                # For now, we will just use the URL if we have it, but we need to figure out the proper way to do this
                # before we release anything
                "id": url or f"urn:uuid:{certificate.uuid}",
                "achievementType": achievement_type,
                "type": ["Achievement"],
                "criteria": {
                    # This will be a markdown list of constituent courses for program certs and the value of the `what_you_learn` field for courserun certs
                    "narrative": narrative
                },
                "description": f"{user_name} has successfully completed all modules and earned a {achievement_type} Certificate in {certificate_name}.",
                "name": certificate_name,
            },
        },
    }
    if achievement_image_url:
        payload["credentialSubject"]["achievement"]["image"] = {
            "id": achievement_image_url,
            "type": "Image",
            "caption": "MIT Learn Certificate logo",
        }
    return payload


def request_verifiable_credential(payload) -> dict:
    headers = {
        "content-type": "application/json",
        "Authorization": f"Bearer {settings.VERIFIABLE_CREDENTIAL_BEARER_TOKEN}",
    }
    resp = requests.post(
        settings.VERIFIABLE_CREDENTIAL_SIGNER_URL,
        json=payload,
        headers=headers,
        timeout=10,
    )
    resp.raise_for_status()

    # Save the returned value as BaseCertificate.verifiable_credential
    return resp.json()


def should_provision_verifiable_credential() -> bool:
    return (
        is_enabled(features.ENABLE_VERIFIABLE_CREDENTIALS_PROVISIONING, False)  # noqa: FBT003
        or settings.ENABLE_VERIFIABLE_CREDENTIALS_PROVISIONING
    )


def create_verifiable_credential(certificate: BaseCertificate, *, raise_on_error=False):
    """
    Create a verifiable credential for the given course run certificate.

    Args:
        certificate (CourseRunCertificate): The course run certificate for which to create the verifiable credential.
        raise_on_error (bool): If True, will re-raise any exceptions encountered during VC creation.
    """
    try:
        if not should_provision_verifiable_credential():
            return
        payload = get_verifiable_credentials_payload(certificate)

        # Call the signing service to create the new credential
        credential = request_verifiable_credential(payload)

        verifiable_credential = VerifiableCredential.objects.create(
            uuid=credential["id"], credential_data=credential
        )
        certificate.verifiable_credential = verifiable_credential
        certificate.save()
    except Exception:
        # We don't want to block certificate creation if VC creation fails, so we swallow and log all errors to sentry
        # We can revisit this later once we've ironed out some of the intended behavior around the json payload
        log.exception(
            "Error creating verifiable credential for certificate %s",
            certificate.uuid,
        )
        if raise_on_error:
            raise
