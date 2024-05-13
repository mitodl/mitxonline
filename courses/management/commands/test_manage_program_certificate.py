"""Tests for Program Certificates management command"""

import factory
import pytest
from django.core.management.base import CommandError

from courses.factories import (
    CourseFactory,
    CourseRunCertificateFactory,
    CourseRunFactory,
    CourseRunGradeFactory,
    ProgramCertificateFactory,
    ProgramFactory,
    program_with_empty_requirements,  # noqa: F401
    program_with_requirements,  # noqa: F401
)
from courses.management.commands import manage_program_certificates
from courses.models import ProgramCertificate
from users.factories import UserFactory

pytestmark = [pytest.mark.django_db]


@pytest.fixture
def edx_grade_json(user):
    return {
        "passed": True,
        "course_id": "test_course_id",
        "username": user.username,
        "percent": 0.5,
    }


def test_program_certificate_management_no_argument():
    """Test that command throws error when no input is provided"""

    with pytest.raises(CommandError) as command_error:
        manage_program_certificates.Command().handle()
    assert (
        str(command_error.value)
        == "The command needs a valid action e.g. --revoke, --unrevoke, --create."
    )


def test_program_certificate_management_invalid_program():
    """
    Test that program certificate management command throws proper error when
    no valid program is supplied
    """

    test_user = UserFactory.create()
    with pytest.raises(CommandError) as command_error:
        manage_program_certificates.Command().handle(
            user=test_user.username, create=True
        )
    assert (
        str(command_error.value) == f"Could not find program with readable_id={None}."
    )

    with pytest.raises(CommandError) as command_error:
        manage_program_certificates.Command().handle(
            user=test_user.username, create=True, program="test"
        )
    assert str(command_error.value) == "Could not find program with readable_id=test."


@pytest.mark.parametrize(
    "username, revoke, unrevoke",  # noqa: PT006
    [
        ("test", True, None),
        ("test", None, True),
    ],
)
def test_program_certificate_management_revoke_unrevoke_invalid_args(
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
    assert (
        str(command_error.value)
        == f"Could not find a user with <username or email>={username}."
    )


@pytest.mark.parametrize(
    "revoke, unrevoke",  # noqa: PT006
    [
        (True, None),
        (None, True),
    ],
)
def test_program_certificate_management_revoke_unrevoke_success(user, revoke, unrevoke):
    """
    Test that program certificate revoke, un-revoke work as
    expected and manage the program certificate access properly
    """
    program = ProgramFactory.create()
    certificate = ProgramCertificateFactory(
        program=program,
        user=user,
        is_revoked=False if revoke else True,  # noqa: SIM211
    )
    manage_program_certificates.Command().handle(
        revoke=revoke,
        unrevoke=unrevoke,
        program=program.readable_id,
        user=user.username,
    )
    certificate.refresh_from_db()
    assert certificate.is_revoked is (True if revoke else False)  # noqa: SIM210
    assert certificate.is_revoked is (False if unrevoke else True)  # noqa: SIM211


def test_program_certificate_management_create(
    user, program_with_empty_requirements, mocker
):
    """
    Test that create operation for program certificate management command
    creates the program certificate for a user
    """
    mocker.patch(
        "hubspot_sync.management.commands.configure_hubspot_properties._upsert_custom_properties",
    )
    courses = CourseFactory.create_batch(2)
    program_with_empty_requirements.add_requirement(courses[0])
    program_with_empty_requirements.add_elective(courses[1])
    course_runs = CourseRunFactory.create_batch(2, course=factory.Iterator(courses))
    CourseRunCertificateFactory.create_batch(
        2, user=user, course_run=factory.Iterator(course_runs)
    )
    manage_program_certificates.Command().handle(
        create=True,
        program=program_with_empty_requirements.readable_id,
        user=user.username,
    )

    generated_certificates = ProgramCertificate.objects.filter(
        user=user, program=program_with_empty_requirements
    )

    assert generated_certificates.count() == 1


def test_program_certificate_management_force_create(
    user, program_with_requirements, mocker
):
    """
    Test that create operation for program certificate management command
    forcefully creates the certificate for a user
    """
    mocker.patch(
        "hubspot_sync.management.commands.configure_hubspot_properties._upsert_custom_properties",
    )
    courses = CourseFactory.create_batch(3)
    course_runs = CourseRunFactory.create_batch(3, course=factory.Iterator(courses))
    CourseRunGradeFactory.create_batch(
        2, course_run=factory.Iterator(course_runs), user=user, passed=False, grade=0
    )
    CourseRunCertificateFactory.create_batch(
        2, user=user, course_run=factory.Iterator(course_runs)
    )
    program_with_requirements.program.add_requirement(courses[0])
    program_with_requirements.program.add_requirement(courses[1])
    program_with_requirements.program.add_requirement(courses[2])
    manage_program_certificates.Command().handle(
        create=True,
        program=program_with_requirements.program.readable_id,
        user=user.username,
        force=True,
    )

    generated_certificates = ProgramCertificate.objects.filter(
        user=user, program=program_with_requirements.program
    )

    assert generated_certificates.count() == 1
