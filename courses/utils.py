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


def get_enrollable_course_run_filter(enrollment_end_date=None, valid_courses=None):
    """
    Returns a queryset of all course runs that are open for enrollment.

    args:
        enrollment_end_date: datetime, the date to check for enrollment end if a future date is needed
        valid_courses: Queryset of Course objects, to filter the course runs by if needed
    """
    now = now_in_utc()
    if enrollment_end_date is None:
        enrollment_end_date = now

    q_filters = (
        Q(live=True)
        & Q(start_date__isnull=False)
        & Q(enrollment_start__lt=now)
        & (Q(enrollment_end=None) | Q(enrollment_end__gt=enrollment_end_date))
    )

    if valid_courses:
        q_filters = q_filters & Q(course__in=valid_courses)

    return q_filters


def get_enrollable_courseruns_qs(enrollment_end_date=None, valid_courses=None):
    """
    Returns all course runs that are open for enrollment.

    args:
        enrollment_end_date: datetime, the date to check for enrollment end if a future date is needed
        valid_courses: Queryset of Course objects, to filter the course runs by if needed
    """
    q_filters = get_enrollable_course_run_filter(enrollment_end_date, valid_courses)

    return CourseRun.objects.filter(q_filters)


def get_unenrollable_courseruns_qs():
    """Returns all course runs that are closed for enrollment."""
    now = now_in_utc()
    return CourseRun.objects.filter(
        Q(live=False)
        | Q(start_date__isnull=True)
        | (Q(enrollment_end__lte=now) | Q(enrollment_start__gt=now))
    )


def get_self_paced_courses(queryset, enrollment_end_date=None):
    """Returns all course runs that are self-paced."""
    now = now_in_utc()
    if enrollment_end_date is None:
        enrollment_end_date = now
    course_ids = queryset.values_list("id", flat=True)
    all_enrollable_runs = get_enrollable_courseruns_qs(valid_courses=course_ids)
    self_paced_runs = all_enrollable_runs.filter(is_self_paced=True)
    return (
        queryset.prefetch_related(Prefetch("courseruns", queryset=self_paced_runs))
        .prefetch_related("courseruns__course")
        .filter(courseruns__id__in=self_paced_runs.values_list("id", flat=True))
        .distinct()
    )


def get_enrollable_courses(queryset, enrollment_end_date=None):
    """
    Returns courses that are open for enrollment

    Args:
        queryset: Queryset of Course objects
        enrollment_end_date: datetime, the date to check for enrollment end if a future date is needed
    """
    if enrollment_end_date is None:
        enrollment_end_date = now_in_utc()
    courseruns_qs = get_enrollable_courseruns_qs(enrollment_end_date)
    return (
        queryset.prefetch_related(Prefetch("courseruns", queryset=courseruns_qs))
        .prefetch_related("courseruns__course")
        .filter(courseruns__id__in=courseruns_qs.values_list("id", flat=True))
        .distinct()
    )


def get_unenrollable_courses(queryset):
    """
    Returns courses that are closed for enrollment

    Args:
        queryset: Queryset of Course objects
    """
    courseruns_qs = get_unenrollable_courseruns_qs()
    return (
        queryset.prefetch_related(Prefetch("courseruns", queryset=courseruns_qs))
        .prefetch_related("courseruns__course")
        .filter(courseruns__id__in=courseruns_qs.values_list("id", flat=True))
        .distinct()
    )


def get_archived_courseruns(queryset):
    """
    Returns course runs that are archived. This is defined as:
    - The course runs are open for enrollment
    - The course run end date has passed
    - The course run enrollment end date is in the future or None.

    Args:
        queryset: Queryset of CourseRun objects
    """
    now = now_in_utc()
    return queryset.filter(
        get_enrollable_course_run_filter(now)
        & Q(end_date__lt=now)
        & (Q(enrollment_end__isnull=True) | Q(enrollment_end__gt=now))
    )


def get_dated_courseruns(queryset):
    """
    Returns course runs that are dated meaning they are
    - Not self-paced
    - Have a start date
    - End date can be dated and greater than now or null
    - Enrollable (enrollment start is in the past and enrollment end is in the future or null)
    """
    return queryset.filter(
        get_enrollable_course_run_filter()
        & Q(is_self_paced=False)
        & Q(enrollment_end__isnull=False)
    )
