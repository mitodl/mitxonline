# pylint:disable=redefined-outer-name
"""
Tests for utils
"""
from datetime import timedelta

from mitol.common.utils import now_in_utc

from courses.factories import (
    CourseFactory,
    CourseRunEnrollmentFactory,
    CourseRunFactory,
    ProgramCertificateFactory,
    ProgramEnrollmentFactory,
    ProgramFactory,  # noqa: F401
    program_with_requirements,  # noqa: F401
)
from courses.models import Course
from courses.utils import (
    get_courses_based_on_enrollment,
    get_enrollable_courseruns_qs,
    get_program_certificate_by_enrollment,
)


def test_get_program_certificate_by_enrollment(user, program_with_requirements):  # noqa: F811
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

    assert get_program_certificate_by_enrollment(course_enrollment) == None  # noqa: E711


def test_get_program_certificate_by_enrollment_program_page_does_not_exist(
    user,
    program_with_requirements,  # noqa: F811
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
    assert get_program_certificate_by_enrollment(course_enrollment, program) == None  # noqa: E711
    assert get_program_certificate_by_enrollment(program_enrollment) == None  # noqa: E711


def test_get_program_certificate_by_enrollment_program_certificate_page_does_not_exist(
    user,
    program_with_requirements,  # noqa: F811
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
    assert get_program_certificate_by_enrollment(course_enrollment) == None  # noqa: E711
    assert get_program_certificate_by_enrollment(program_enrollment) == None  # noqa: E711


def test_get_enrollable_courseruns_qs():
    """
    Test get_enrollable_courseruns_qs
    """
    course = CourseFactory.create()
    now = now_in_utc()
    future_date = now + timedelta(days=1)
    past_date = now - timedelta(days=1)
    course_run = CourseRunFactory.create(
        course=course,
        live=True,
        start_date=now,
        enrollment_start=past_date,
        enrollment_end=future_date,
    )
    CourseRunFactory.create(
        course=course,
        live=True,
        start_date=now,
        enrollment_start=past_date,
        enrollment_end=future_date,
    )

    enrollable_qs = get_enrollable_courseruns_qs()
    assert enrollable_qs.count() == 2
    assert course_run in enrollable_qs

    unenrollable_course_run = CourseFactory.create(
        course=course,
        live=True,
        start_date=now,
        enrollment_start=future_date,
        enrollment_end=None,
    )
    enrollable_qs = get_enrollable_courseruns_qs()
    assert enrollable_qs.count() == 2
    assert course_run in enrollable_qs
    assert unenrollable_course_run not in enrollable_qs


def test_get_unenrollable_courseruns_qs():
    """
    Test get_enrollable_courseruns_qs
    """
    course = CourseFactory.create()
    now = now_in_utc()
    future_date = now + timedelta(days=1)
    past_date = now - timedelta(days=1)
    course_run = CourseRunFactory.create(
        course=course,
        live=True,
        start_date=now,
        enrollment_start=past_date,
        enrollment_end=future_date,
    )
    CourseRunFactory.create(
        course=course,
        live=True,
        start_date=now,
        enrollment_start=past_date,
        enrollment_end=future_date,
    )

    enrollable_qs = get_enrollable_courseruns_qs()
    assert enrollable_qs.count() == 0
    assert course_run not in enrollable_qs

    unenrollable_course_run = CourseFactory.create(
        course=course,
        live=True,
        start_date=future_date,
        enrollment_start=future_date,
        enrollment_end=None,
    )
    enrollable_qs = get_enrollable_courseruns_qs()
    assert enrollable_qs.count() == 1
    assert course_run not in enrollable_qs
    assert unenrollable_course_run in enrollable_qs


def test_get_courses_based_on_enrollment():
    """
    Test get_courses_based_on_enrollment
    """
    now = now_in_utc()
    future_date = now + timedelta(days=1)
    past_date = now - timedelta(days=1)
    course = CourseFactory.create()
    unenrollable_course = CourseFactory.create()
    CourseRunFactory.create(
        course=course,
        live=True,
        start_date=now,
        enrollment_start=past_date,
        enrollment_end=future_date,
    )
    CourseRunFactory.create(
        course=unenrollable_course,
        live=True,
        start_date=future_date,
        enrollment_start=future_date,
        enrollment_end=None,
    )
    can_enroll = get_courses_based_on_enrollment(Course.objects.all(), True)
    assert unenrollable_course not in can_enroll
    assert course in can_enroll
    can_not_enroll = get_courses_based_on_enrollment(Course.objects.all(), False)
    assert unenrollable_course in can_not_enroll
    assert course not in can_not_enroll
