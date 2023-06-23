# pylint:disable=redefined-outer-name
"""
Tests for utils
"""
import pytest

from courses.factories import (
    CourseFactory,
    CourseRunEnrollmentFactory,
    CourseRunFactory,
    ProgramCertificateFactory,
    ProgramEnrollmentFactory,
    ProgramFactory,
    program_with_requirements,
)
from courses.utils import get_program_certificate_by_enrollment


def test_get_program_certificate_by_enrollment(user, program_with_requirements):
    """
    Test that get_program_certificate_by_enrollment returns a program certificate
    """
    course = program_with_requirements.program.courses[0][0]
    course_run = CourseRunFactory.create(course=course)

    course_enrollment = CourseRunEnrollmentFactory.create(user=user, run=course_run)
    program_enrollment = ProgramEnrollmentFactory.create(
        user=user, program=program_with_requirements.program
    )

    program_certificate = ProgramCertificateFactory.create(
        program=program_with_requirements.program, user=user
    )

    program_with_requirements.program.refresh_from_db()

    assert (
        get_program_certificate_by_enrollment(
            course_enrollment, program_with_requirements.program
        )
        == program_certificate
    )
    assert (
        get_program_certificate_by_enrollment(program_enrollment) == program_certificate
    )


def test_get_program_certificate_by_enrollment_program_does_not_exist(user):
    """
    Test that get_program_certificate_by_enrollment returns None if course has no program
    """
    course = CourseFactory.create()
    course_run = CourseRunFactory.create(course=course)

    course_enrollment = CourseRunEnrollmentFactory.create(user=user, run=course_run)

    assert get_program_certificate_by_enrollment(course_enrollment) == None


def test_get_program_certificate_by_enrollment_program_page_does_not_exist(
    user, program_with_requirements
):
    """
    Test that get_program_certificate_by_enrollment returns None if program page does not exist
    """
    program = program_with_requirements.program

    program.page.delete()

    course = program_with_requirements.program.courses[0][0]
    course_run = CourseRunFactory.create(course=course)

    course_enrollment = CourseRunEnrollmentFactory.create(user=user, run=course_run)
    program_enrollment = ProgramEnrollmentFactory.create(user=user, program=program)

    program_certificate = ProgramCertificateFactory.create(program=program, user=user)

    assert (
        get_program_certificate_by_enrollment(course_enrollment, program)
        != program_certificate
    )
    assert (
        get_program_certificate_by_enrollment(program_enrollment) != program_certificate
    )
    assert get_program_certificate_by_enrollment(course_enrollment, program) == None
    assert get_program_certificate_by_enrollment(program_enrollment) == None


def test_get_program_certificate_by_enrollment_program_certificate_page_does_not_exist(
    user, program_with_requirements
):
    """
    Test that get_program_certificate_by_enrollment returns None if program certificate page does not exist
    """
    program = program_with_requirements.program

    program.page.certificate_page.delete()
    program.page.delete()

    course = program_with_requirements.program.courses[0][0]
    course_run = CourseRunFactory.create(course=course)

    course_enrollment = CourseRunEnrollmentFactory.create(user=user, run=course_run)
    program_enrollment = ProgramEnrollmentFactory.create(user=user, program=program)

    program_certificate = ProgramCertificateFactory.create(program=program, user=user)

    assert (
        get_program_certificate_by_enrollment(course_enrollment) != program_certificate
    )
    assert (
        get_program_certificate_by_enrollment(program_enrollment) != program_certificate
    )
    assert get_program_certificate_by_enrollment(course_enrollment) == None
    assert get_program_certificate_by_enrollment(program_enrollment) == None
