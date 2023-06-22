"""Utilities for courses"""

import logging
from requests.exceptions import HTTPError
from courses.models import (
    CourseRunEnrollment,
    ProgramCertificate,
)


log = logging.getLogger(__name__)


def exception_logging_generator(generator):
    """Returns a new generator that logs exceptions from the given generator and continues with iteration"""
    while True:
        try:
            yield next(generator)
        except StopIteration:
            return
        except HTTPError as exc:
            log.exception("EdX API error for fetching user grades %s:", exc)
        except Exception as exp:  # pylint: disable=broad-except
            log.exception("Error fetching user grades from edX %s:", exp)


def is_grade_valid(override_grade: float):
    return 0.0 <= override_grade <= 1.0


def get_program_certificate_by_enrollment(enrollment):
    """
    Resolve a certificate for this enrollment if it exists
    """
    user_id = enrollment.user_id
    if isinstance(enrollment, CourseRunEnrollment):
        # No need to include a certificate if there is no corresponding wagtail page
        # to support the render
        if (
            not enrollment.run.course.program
            or not hasattr(enrollment.run.course.program, "page")
            or not enrollment.run.course.program.page
            or not enrollment.run.course.program.page.certificate_page
        ):
            return None
        program_id = enrollment.run.course.program.id
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


def convert_to_letter(grade):
    """Convert a decimal number to letter grade"""
    grade = round(grade, 1)
    if grade >= 0.825:
        return "A"
    elif grade >= 0.65:
        return "B"
    elif grade >= 0.55:
        return "C"
    elif grade >= 0.50:
        return "D"
    else:
        return "F"
