"""Utilities for courses"""

import logging
from requests.exceptions import HTTPError
from courses.models import (
    CourseRunCertificate,
    CourseRunEnrollment,
    ProgramCertificate,
    ProgramEnrollment,
    ProgramRequirement,
    ProgramRequirementNodeType,
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


def generate_program_certificate(user, program):
    """
    Create a program certificate if the user has a course certificate
    for each course in the program. Also, It will create the
    program enrollment if it does not exist for the user.

    Args:
        user (User): a Django user.
        program (programs.models.Program): program where the user is enrolled.

    Returns:
        (ProgramCertificate or None, bool): A tuple containing a
        ProgramCertificate (or None if one was not found or created) paired
        with a boolean indicating whether the certificate was newly created.
    """
    existing_cert_queryset = ProgramCertificate.objects.filter(
        user=user, program=program
    )
    if existing_cert_queryset.exists():
        ProgramEnrollment.objects.get_or_create(
            program=program, user=user, defaults={"active": True, "change_status": None}
        )
        return existing_cert_queryset.first(), False

    courses_in_program_ids = set(
        program.get_requirements_root()
        .get_children()
        .filter(operator=ProgramRequirement.Operator.ALL_OF)
        .first()
        .get_children()
        .filter(node_type=ProgramRequirementNodeType.COURSE)
        .values_list("course_id", flat=True)
    )
    # courses_in_program_ids = set(program.courses.values_list("id", flat=True))
    num_courses_with_cert = (
        CourseRunCertificate.objects.filter(
            user=user, course_run__course_id__in=courses_in_program_ids
        )
        .distinct()
        .count()
    )

    if len(courses_in_program_ids) > num_courses_with_cert:
        return None, False

    program_cert = ProgramCertificate.objects.create(user=user, program=program)
    if program_cert:
        log.info(
            "Program certificate for [%s] in program [%s] is created.",
            user.username,
            program.title,
        )
        _, created = ProgramEnrollment.objects.get_or_create(
            program=program, user=user, defaults={"active": True, "change_status": None}
        )

        if created:
            log.info(
                "Program enrollment for [%s] in program [%s] is created.",
                user.username,
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
