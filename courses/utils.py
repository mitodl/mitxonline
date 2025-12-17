"""Utilities for courses"""

import logging
import re
from urllib.parse import urljoin

from django.db.models import Prefetch, Q
from mitol.common.utils.datetime import now_in_utc
from requests.exceptions import HTTPError

from courses.constants import UAI_COURSEWARE_ID_PREFIX
from courses.models import (
    CourseRun,
    CourseRunEnrollment,
    CourseRunQuerySet,
    ProgramCertificate,
)
from main import settings

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


def get_enrollable_courseruns_qs(enrollment_end_date=None, valid_courses=None):
    """
    Returns all course runs that are open for enrollment.

    args:
        enrollment_end_date: datetime, the date to check for enrollment end if a future date is needed
        valid_courses: Queryset of Course objects, to filter the course runs by if needed
    """
    queryset = CourseRun.objects.enrollable(enrollment_end_date)

    if valid_courses:
        queryset = queryset.filter(course__in=valid_courses)

    return queryset


def get_enrollable_courses(queryset, enrollment_end_date=None):
    """
    Returns courses that are open for enrollment

    Args:
        queryset: Queryset of Course objects
        enrollment_end_date: datetime, the date to check for enrollment end if a future date is needed
    """
    enrollable_courseruns_qs = CourseRun.objects.enrollable(enrollment_end_date)

    return (
        queryset.prefetch_related(
            Prefetch("courseruns", queryset=enrollable_courseruns_qs)
        )
        .filter(
            courseruns__id__in=enrollable_courseruns_qs.values_list("id", flat=True)
        )
        .distinct()
    )


def get_unenrollable_courses(queryset):
    """
    Returns courses that are closed for enrollment

    Args:
        queryset: Queryset of Course objects
    """
    courseruns_qs = CourseRun.objects.unenrollable()
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
        CourseRunQuerySet.get_enrollable_filter(now)
        & Q(end_date__lt=now)
        & (Q(enrollment_end__isnull=True) | Q(enrollment_end__gt=now))
    )


def get_dated_courseruns(queryset):
    """
    Returns course runs that are dated meaning they are
    - Enrollable (see get_enrollable_filter for more details)
    - Not self-paced
    """
    return queryset.filter(
        CourseRunQuerySet.get_enrollable_filter() & Q(is_self_paced=False)
    )


def is_uai_course_run(course_run):
    """
    Check if a course run is a UAI course run.

    Args:
        course_run: CourseRun instance

    Returns:
        bool: True if the course run is UAI, False otherwise
    """
    if not course_run or not course_run.courseware_id:
        return False

    return course_run.courseware_id.startswith(UAI_COURSEWARE_ID_PREFIX)


def is_uai_order(order):
    """
    Check if an order contains any UAI courses.

    Args:
        order: Order instance

    Returns:
        bool: True if the order contains UAI courses, False otherwise
    """
    for line in order.lines.all():
        if hasattr(line.product, "purchasable_object"):
            course_run = line.product.purchasable_object
            if hasattr(course_run, "courseware_id") and is_uai_course_run(course_run):
                return True
    return False


def get_approved_flexible_price_exists(instance, context):
    """
    Check if an approved flexible price exists for a given instance and context.

    This utility function consolidates the logic for checking flexible pricing approval
    across different serializer contexts.

    Args:
        instance: The model instance (CourseRun, CourseRunEnrollment, or list of enrollments)
        context: Serializer context dictionary

    Returns:
        bool: True if an approved flexible price exists, False otherwise
    """
    # Import here to avoid circular dependency
    from flexiblepricing.api import is_courseware_flexible_price_approved

    # Handle different instance types to extract course/run and user
    if isinstance(instance, list):
        # Handle list of enrollments (from BaseCourseRunEnrollmentSerializer.create)
        if not instance:
            return False
        enrollment = instance[0]
        course_or_run = enrollment.run
        check_user = enrollment.user
    elif hasattr(instance, "run"):
        # Handle CourseRunEnrollment instance
        course_or_run = instance.run
        check_user = instance.user
    elif hasattr(instance, "course"):
        # Handle CourseRun instance - need user from context
        # Early return if context doesn't require flexible pricing check
        if not context or not context.get("include_approved_financial_aid"):
            return False
        user = context.get("request", {}).user if "request" in context else None
        if not user or not user.id:
            return False
        course_or_run = instance.course
        check_user = user
    else:
        # Handle Course instance directly - need user from context
        # Early return if context doesn't require flexible pricing check
        if not context or not context.get("include_approved_financial_aid"):
            return False
        user = context.get("request", {}).user if "request" in context else None
        if not user or not user.id:
            return False
        course_or_run = instance
        check_user = user

    return is_courseware_flexible_price_approved(course_or_run, check_user)


def dc_url(path):
    """Returns the full url to the provided path"""
    return urljoin(settings.DIGITAL_CREDENTAL_COORDINATOR_URL, path)
