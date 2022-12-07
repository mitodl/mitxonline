# pylint:disable=redefined-outer-name
"""
Tests for utils
"""
import factory

from courses.factories import (
    CourseFactory,
    CourseRunCertificateFactory,
    CourseRunEnrollmentFactory,
    CourseRunFactory,
    CourseRunGradeFactory,
    ProgramCertificateFactory,
    ProgramEnrollmentFactory,
    ProgramRequirementFactory,
    ProgramFactory,
)
from courses.models import (
    ProgramCertificate,
)
from courses.utils import (
    generate_program_certificate,
    get_program_certificate_by_enrollment,
)


def test_generate_program_certificate_failure_missing_certificates(user, program):
    """
    Test that generate_program_certificate return (None, False) and not create program certificate
    if there is not any course_run certificate for the given course.
    """
    course = CourseFactory.create(program=program)
    CourseRunFactory.create_batch(3, course=course)
    ProgramRequirementFactory.add_root(program)
    program.add_requirement(course)

    result = generate_program_certificate(user=user, program=program)
    assert result == (None, False)
    assert len(ProgramCertificate.objects.all()) == 0


def test_generate_program_certificate_failure_not_all_passed(user, program):
    """
    Test that generate_program_certificate return (None, False) and not create program certificate
    if there is not any course_run certificate for the given course.
    """
    courses = CourseFactory.create_batch(3, program=program)
    course_runs = CourseRunFactory.create_batch(3, course=factory.Iterator(courses))
    CourseRunCertificateFactory.create_batch(
        2, user=user, course_run=factory.Iterator(course_runs)
    )
    ProgramRequirementFactory.add_root(program)
    program.add_requirement(courses[0])
    program.add_requirement(courses[1])
    program.add_requirement(courses[2])

    result = generate_program_certificate(user=user, program=program)
    assert result == (None, False)
    assert len(ProgramCertificate.objects.all()) == 0


def test_generate_program_certificate_success(user, program):
    """
    Test that generate_program_certificate generate a program certificate
    """
    course = CourseFactory.create(program=program)
    ProgramRequirementFactory.add_root(program)
    program.add_requirement(course)
    course_run = CourseRunFactory.create(course=course)
    CourseRunGradeFactory.create(course_run=course_run, user=user, passed=True, grade=1)

    CourseRunCertificateFactory.create(user=user, course_run=course_run)

    certificate, created = generate_program_certificate(user=user, program=program)
    assert created is True
    assert isinstance(certificate, ProgramCertificate)
    assert len(ProgramCertificate.objects.all()) == 1


def test_generate_program_certificate_already_exist(user, program):
    """
    Test that generate_program_certificate return (None, False) and not create program certificate
    if program certificate already exist.
    """
    program_certificate = ProgramCertificateFactory.create(program=program, user=user)
    result = generate_program_certificate(user=user, program=program)
    assert result == (program_certificate, False)
    assert len(ProgramCertificate.objects.all()) == 1


def test_get_program_certificate_by_enrollment(user, program):
    """
    Test that get_program_certificate_by_enrollment returns a program certificate
    """
    course = CourseFactory.create(program=program)
    course_run = CourseRunFactory.create(course=course)

    course_enrollment = CourseRunEnrollmentFactory.create(user=user, run=course_run)
    program_enrollment = ProgramEnrollmentFactory.create(user=user, program=program)

    program_certificate = ProgramCertificateFactory.create(program=program, user=user)

    assert (
        get_program_certificate_by_enrollment(course_enrollment) == program_certificate
    )
    assert (
        get_program_certificate_by_enrollment(program_enrollment) == program_certificate
    )


def test_get_program_certificate_by_enrollment_program_does_not_exist(user):
    """
    Test that get_program_certificate_by_enrollment returns None if course has no program
    """
    course = CourseFactory.create(program=None)
    course_run = CourseRunFactory.create(course=course)

    course_enrollment = CourseRunEnrollmentFactory.create(user=user, run=course_run)

    assert get_program_certificate_by_enrollment(course_enrollment) == None


def test_get_program_certificate_by_enrollment_program_page_does_not_exist(user):
    """
    Test that get_program_certificate_by_enrollment returns None if program page does not exist
    """
    course = CourseFactory.create()
    program = course.program
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


def test_get_program_certificate_by_enrollment_program_certificate_page_does_not_exist(
    user,
):
    """
    Test that get_program_certificate_by_enrollment returns None if program certificate page does not exist
    """
    program = ProgramFactory(page__certificate_page=None)
    course = CourseFactory.create(program=program)
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
