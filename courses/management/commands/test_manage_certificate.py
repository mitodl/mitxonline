"""Tests for Certificates management command"""

import pytest
import factory
from courses.management.commands import manage_certificates
from courses.models import CourseRun, CourseRunCertificate, CourseRunGrade
from django.core.management.base import CommandError
from users.factories import UserFactory
from courses.factories import (
    CourseRunFactory,
    CourseRunCertificateFactory,
    CourseRunEnrollmentFactory,
)
from openedx.constants import EDX_DEFAULT_ENROLLMENT_MODE, EDX_ENROLLMENT_VERIFIED_MODE
from edx_api.grades.models import CurrentGrade

pytestmark = [pytest.mark.django_db]


@pytest.fixture
def edx_grade_json(user):
    return {
        "passed": True,
        "course_id": "test_course_id",
        "username": user.username,
        "percent": 0.5,
    }


def test_certificate_management_no_argument():
    """Test that command throws error when no input is provided"""

    with pytest.raises(CommandError) as command_error:
        manage_certificates.Command().handle()
    assert (
        str(command_error.value)
        == "The command needs a valid action e.g. --revoke, --unrevoke, --create"
    )


def test_certificate_management_invalid_run():
    """Test that certificate management command throws proper error when no valid run is supplied"""

    test_user = UserFactory.create()
    with pytest.raises(CommandError) as command_error:
        manage_certificates.Command().handle(user=test_user.username, create=True)
    assert str(command_error.value) == "The command needs a valid course run"

    with pytest.raises(CommandError) as command_error:
        manage_certificates.Command().handle(
            user=test_user.username, create=True, run="test"
        )
    assert str(command_error.value) == "Could not find run with courseware_id=test"


def test_certificate_override_grade_no_user():
    """Test that overriding grade for all users is not supported"""

    course_run = CourseRunFactory.create()
    with pytest.raises(CommandError) as command_error:
        manage_certificates.Command().handle(
            create=True, run=course_run.courseware_id, grade=0.5, user=None
        )
    assert (
        str(command_error.value)
        == "Override grade needs a user (The grade override operation is not supported for multiple users)"
    )


@pytest.mark.parametrize(
    "username, revoke, unrevoke",
    [
        (None, True, None),
        ("test", True, None),
        (None, None, True),
        ("test", None, True),
    ],
)
def test_certificate_management_revoke_unrevoke_invalid_args(
    username, revoke, unrevoke
):
    """Test that the command throws proper error when revoke, un-revoke operations are not given proper arguments"""
    course_run = CourseRunFactory.create()

    with pytest.raises(CommandError) as command_error:
        manage_certificates.Command().handle(
            user=username,
            revoke=revoke,
            unrevoke=unrevoke,
            run=course_run.courseware_id,
        )
    assert str(command_error.value) == "Revoke/Un-revoke operation needs a valid user"


@pytest.mark.parametrize(
    "revoke, unrevoke",
    [
        (True, None),
        (None, True),
    ],
)
def test_certificate_management_revoke_unrevoke_success(user, revoke, unrevoke):
    """Test that certificate revoke, un-revoke work as expected and manage the certificate access properly"""
    course_run = CourseRunFactory.create()
    certificate = CourseRunCertificateFactory(
        course_run=course_run, user=user, is_revoked=False if revoke else True
    )
    manage_certificates.Command().handle(
        revoke=revoke,
        unrevoke=unrevoke,
        run=course_run.courseware_id,
        user=user.username,
    )
    certificate.refresh_from_db()
    assert certificate.is_revoked is (True if revoke else False)
    assert certificate.is_revoked is (False if unrevoke else True)


def test_certificate_management_create(mocker, user, edx_grade_json):
    """Test that create operation for certificate management command creates the certificates for a single user
    when a user is provided"""
    edx_grade = CurrentGrade(edx_grade_json)
    course_run = CourseRunFactory.create()
    CourseRunEnrollmentFactory.create(
        user=user, run=course_run, enrollment_mode=EDX_ENROLLMENT_VERIFIED_MODE
    )

    mocker.patch(
        "courses.management.commands.manage_certificates.get_edx_grades_with_users",
        return_value=[
            (edx_grade, user),
        ],
    )
    manage_certificates.Command().handle(
        create=True, run=course_run.courseware_id, user=user.username
    )

    generated_certificates = CourseRunCertificate.objects.filter(
        user=user, course_run=course_run
    )
    generated_grades = CourseRunGrade.objects.filter(user=user, course_run=course_run)

    assert generated_certificates.count() == 1
    assert generated_grades.count() == 1


def test_certificate_management_create_no_user(mocker, edx_grade_json, user):
    """Test that create operation for certificate management command attempts to creates the certificates for all the
    enrolled users in a run when no user is provided"""
    passed_edx_grade = CurrentGrade(edx_grade_json)
    course_run = CourseRunFactory.create()
    users = UserFactory.create_batch(4)
    CourseRunEnrollmentFactory.create_batch(
        3,
        user=factory.Iterator(users),
        run=course_run,
        enrollment_mode=EDX_ENROLLMENT_VERIFIED_MODE,
    )
    CourseRunEnrollmentFactory.create(
        user=users[3], run=course_run, enrollment_mode=EDX_DEFAULT_ENROLLMENT_MODE
    )

    mocker.patch(
        "courses.management.commands.manage_certificates.get_edx_grades_with_users",
        return_value=[
            (passed_edx_grade, users[0]),
            (passed_edx_grade, users[1]),
            (passed_edx_grade, users[2]),
            (passed_edx_grade, users[3]),
        ],
    )
    manage_certificates.Command().handle(
        create=True, run=course_run.courseware_id, user=None
    )

    generated_certificates = CourseRunCertificate.objects.filter(course_run=course_run)
    generated_grades = CourseRunGrade.objects.filter(course_run=course_run)

    assert generated_certificates.count() == 3
    assert generated_grades.count() == 4
