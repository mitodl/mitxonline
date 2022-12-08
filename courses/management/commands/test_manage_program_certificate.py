"""Tests for Certificates management command"""

import pytest
from courses.management.commands import manage_program_certificates
from courses.models import ProgramCertificate
from django.core.management.base import CommandError
from users.factories import UserFactory
from courses.factories import (
    CourseFactory,
    CourseRunFactory,
    CourseRunGradeFactory,
    CourseRunCertificateFactory,
    ProgramFactory,
    ProgramCertificateFactory,
    ProgramRequirementFactory,
)

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
        manage_program_certificates.Command().handle()
    assert (
        str(command_error.value)
        == "The command needs a valid action e.g. --revoke, --unrevoke, --create."
    )


def test_certificate_management_invalid_program():
    """Test that certificate management command throws proper error when no valid program is supplied"""

    test_user = UserFactory.create()
    with pytest.raises(CommandError) as command_error:
        manage_program_certificates.Command().handle(
            user=test_user.username, create=True
        )
    assert str(command_error.value) == "The command needs a valid program."

    with pytest.raises(CommandError) as command_error:
        manage_program_certificates.Command().handle(
            user=test_user.username, create=True, program="test"
        )
    assert str(command_error.value) == "Could not find program with readable_id=test."


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
    program = ProgramFactory.create()

    with pytest.raises(CommandError) as command_error:
        manage_program_certificates.Command().handle(
            user=username,
            revoke=revoke,
            unrevoke=unrevoke,
            program=program.readable_id,
        )
    assert str(command_error.value) == "Revoke/Un-revoke operation needs a valid user."


@pytest.mark.parametrize(
    "revoke, unrevoke",
    [
        (True, None),
        (None, True),
    ],
)
def test_certificate_management_revoke_unrevoke_success(user, revoke, unrevoke):
    """Test that certificate revoke, un-revoke work as expected and manage the certificate access properly"""
    program = ProgramFactory.create()
    certificate = ProgramCertificateFactory(
        program=program, user=user, is_revoked=False if revoke else True
    )
    manage_program_certificates.Command().handle(
        revoke=revoke,
        unrevoke=unrevoke,
        program=program.readable_id,
        user=user.username,
    )
    certificate.refresh_from_db()
    assert certificate.is_revoked is (True if revoke else False)
    assert certificate.is_revoked is (False if unrevoke else True)


def test_certificate_management_create(user):
    """Test that create operation for certificate management command creates the certificates for a single user
    when a user is provided"""
    program = ProgramFactory.create()
    course = CourseFactory.create(program=program)
    ProgramRequirementFactory.add_root(program)
    program.add_requirement(course)
    course_run = CourseRunFactory.create(course=course)
    CourseRunGradeFactory.create(course_run=course_run, user=user, passed=True, grade=1)
    CourseRunCertificateFactory.create(user=user, course_run=course_run)
    manage_program_certificates.Command().handle(
        create=True, program=program.readable_id, user=user.username
    )

    generated_certificates = ProgramCertificate.objects.filter(
        user=user, program=program
    )

    assert generated_certificates.count() == 1
