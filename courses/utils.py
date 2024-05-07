"""Utilities for courses"""

import logging
import re

from django.db.models import Prefetch, Q
from mitol.common.utils.datetime import now_in_utc
from requests.exceptions import HTTPError

from courses.models import CourseRun, CourseRunEnrollment, ProgramCertificate

log = logging.getLogger(__name__)


def exception_logging_generator(generator):
    """Returns a new generator that logs exceptions from the given generator and continues with iteration"""
    while True:
        try:
            yield next(generator)
        except StopIteration:  # noqa: PERF203
            return
        except HTTPError as exc:
            log.exception("EdX API error for fetching user grades %s:", exc)  # noqa: TRY401
        except Exception as exp:  # pylint: disable=broad-except
            log.exception("Error fetching user grades from edX %s:", exp)  # noqa: TRY401


def is_grade_valid(override_grade: float):
    return 0.0 <= override_grade <= 1.0


def is_letter_grade_valid(letter_grade: str):
    return re.match("^[A-F]$", letter_grade) is not None


def get_program_certificate_by_enrollment(enrollment, program=None):
    """
    Resolve a certificate for this enrollment and program if it exists

    This requires a program to be passed along with a CourseRunEnrollment, or
    we won't be able to tell which of the course's programs to look for
    certificates for.

    Args:
    - enrollment: CourseRunEnrollment or ProgramEnrollment, the courseware ID to look for program certificates for
    - program: Program or None, the program to consider in the case of a CourseRunEnrollment

    Returns:
    - ProgramCertificate or None
    """
    user_id = enrollment.user_id
    if isinstance(enrollment, CourseRunEnrollment):
        # No need to include a certificate if there is no corresponding wagtail page
        # to support the render
        if (
            not hasattr(program, "page")
            or not program.page
            or not program.page.certificate_page
        ):
            return None
        program_id = program.id
    else:
        # No need to include a certificate if there is no corresponding wagtail page
        # to support the render
        if (
            not hasattr(enrollment.program, "page")
            or not enrollment.program.page
            or not enrollment.program.page.certificate_page
        ):
            return None
        program_id = enrollment.program_id
    # Using IDs because we don't need the actual record and this avoids redundant queries
    try:
        return ProgramCertificate.objects.get(user_id=user_id, program_id=program_id)
    except ProgramCertificate.DoesNotExist:
        return None


def get_enrollable_courseruns_qs(enrollment_end_date):
    """Returns all course runs that are open for enrollment."""
    now = now_in_utc()
    return CourseRun.objects.filter(
        Q(live=True)
        & Q(start_date__isnull=False)
        & Q(enrollment_start__lt=now)
        & (Q(enrollment_end=None) | Q(enrollment_end__gt=enrollment_end_date))
    )


def get_unenrollable_courseruns_qs():
    """Returns all course runs that are closed for enrollment."""
    now = now_in_utc()
    return CourseRun.objects.filter(
        Q(live=False) | Q(start_date__isnull=True) | (Q(enrollment_end__lte=now))
    )


def get_courses_based_on_enrollment(
    queryset, enrollable=True, enrollment_end_date=None
):
    """
    Returns courses based on the current enrollment status

    Args:
        queryset: Queryset of Course objects
        enrollable: Boolean, if True, returns courses that are open for enrollment,
                    otherwise returns courses that are closed for enrollment
        enrollment_end_date: datetime, the date to check for enrollment end
    """
    if enrollment_end_date is None:
        enrollment_end_date = now_in_utc()
    if enrollable:
        courseruns_qs = get_enrollable_courseruns_qs(enrollment_end_date)
    else:
        courseruns_qs = get_unenrollable_courseruns_qs()
    return (
        queryset.prefetch_related(Prefetch("courseruns", queryset=courseruns_qs))
        .prefetch_related("courseruns__course")
        .filter(courseruns__id__in=courseruns_qs.values_list("id", flat=True))
        .distinct()
    )
