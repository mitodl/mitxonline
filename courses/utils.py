"""Utilities for courses"""

import logging
import re

from requests.exceptions import HTTPError

from courses.models import CourseRunEnrollment, ProgramCertificate

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
