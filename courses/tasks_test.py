"""Tests for Course related tasks"""

import pytest

from courses.factories import (
    CourseRunFactory,
    CourseRunGradeFactory,
    CourseRunEnrollmentFactory,
)
from courses.tasks import subscribe_edx_course_emails, generate_course_certificates

from mitol.common.utils.datetime import now_in_utc
from datetime import timedelta
from openedx.constants import EDX_ENROLLMENT_VERIFIED_MODE

pytestmark = pytest.mark.django_db


@pytest.fixture()
def tasks_log(mocker):
    """Logger fixture for tasks"""
    return mocker.patch("courses.tasks.log")


@pytest.fixture()
def course_run():
    """Fixture to produce a course run"""
    return CourseRunFactory.create()


@pytest.fixture
def paid_enrollment(user, course_run):
    """Fixture to produce a paid enrollment"""
    return CourseRunEnrollmentFactory.create(
        user=user, run=course_run, enrollment_mode=EDX_ENROLLMENT_VERIFIED_MODE
    )


@pytest.fixture()
def passed_grade_enrollment(paid_enrollment):
    """Fixture to produce a passed CourseRunGrade"""
    return CourseRunGradeFactory.create(
        course_run=paid_enrollment.run,
        user=paid_enrollment.user,
        grade=0.50,
        passed=True,
    )


def test_subscribe_edx_course_emails(mocker, user):
    """Test that subscribe_edx_course_emails task updates the state correctly after subscribing to edX emails"""
    enrollment = CourseRunEnrollmentFactory.create(
        user=user, edx_enrolled=True, active=True, edx_emails_subscription=False
    )
    subscribe_edx_emails_patch = mocker.patch(
        "openedx.api.subscribe_to_edx_course_emails", return_value=True
    )

    subscribe_edx_course_emails.delay(enrollment_id=enrollment.id)

    subscribe_edx_emails_patch.assert_called_once()
    enrollment.refresh_from_db()
    assert enrollment.edx_emails_subscription is True


def test_generate_course_certificates_no_valid_course_run(settings, tasks_log):
    """Test that a proper message is logged when there is no valid course run to generate certificates"""
    generate_course_certificates()
    assert (
        "No course runs matched the certificates generation criteria"
        in tasks_log.info.call_args[0][0]
    )

    # Create a batch of Course Runs that doesn't match certificate generation filter
    CourseRunFactory.create_batch(
        5,
        self_paced_certificates=False,
        end_date=now_in_utc()
        - timedelta(hours=settings.CERTIFICATE_CREATION_DELAY_IN_HOURS + 1),
    )
    generate_course_certificates()
    assert (
        "No course runs matched the certificates generation criteria"
        in tasks_log.info.call_args[0][0]
    )


def test_generate_course_certificates_self_paced_course(
    mocker, tasks_log, passed_grade_enrollment
):
    """Test that certificates are generated for self paced course runs independent of course run end date"""
    course_run = passed_grade_enrollment.course_run
    user = passed_grade_enrollment.user
    course_run.self_paced_certificates = True
    course_run.save()

    mocker.patch(
        "courses.api.ensure_course_run_grade",
        return_value=(passed_grade_enrollment, True, False),
    )
    mocker.patch(
        "courses.tasks.exception_logging_generator",
        return_value=[(passed_grade_enrollment, user)],
    )
    generate_course_certificates()
    assert (
        f"Finished processing course run {course_run}: created grades for {1} users, updated grades for {0} users, generated certificates for {1} users"
        in tasks_log.info.call_args[0][0]
    )


def test_generate_course_certificates_with_course_end_date(
    mocker, tasks_log, passed_grade_enrollment, settings
):
    """Test that certificates are generated for passed grades when there are valid course runs for certificates"""
    settings.CERTIFICATE_CREATION_DELAY_IN_HOURS = 1
    course_run = passed_grade_enrollment.course_run
    course_run.end_date = now_in_utc()
    course_run.save()

    user = passed_grade_enrollment.user

    mocker.patch(
        "courses.api.ensure_course_run_grade",
        return_value=(passed_grade_enrollment, True, False),
    )
    mocker.patch(
        "courses.tasks.exception_logging_generator",
        return_value=[(passed_grade_enrollment, user)],
    )
    generate_course_certificates()
    assert (
        f"Finished processing course run {course_run}: created grades for {1} users, updated grades for {0} users, generated certificates for {1} users"
        in tasks_log.info.call_args[0][0]
    )


@pytest.mark.parametrize(
    "self_paced, end_date",
    [
        (True, now_in_utc() + timedelta(hours=2)),
        (False, now_in_utc()),
    ],
)
def test_course_certificates_with_course_end_date_self_paced_combination(
    mocker, settings, tasks_log, passed_grade_enrollment, self_paced, end_date
):
    """Test that correct certificates are created when there are course runs with end_date and self_paced combination"""
    settings.CERTIFICATE_CREATION_DELAY_IN_HOURS = 1
    course_run = passed_grade_enrollment.course_run
    course_run.self_paced_certificates = self_paced
    course_run.end_date = end_date
    course_run.save()

    user = passed_grade_enrollment.user

    mocker.patch(
        "courses.api.ensure_course_run_grade",
        return_value=(passed_grade_enrollment, True, False),
    )
    mocker.patch(
        "courses.tasks.exception_logging_generator",
        return_value=[(passed_grade_enrollment, user)],
    )
    generate_course_certificates()
    assert (
        f"Finished processing course run {course_run}: created grades for {1} users, updated grades for {0} users, generated certificates for {1} users"
        in tasks_log.info.call_args[0][0]
    )
