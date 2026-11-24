"""Tests for Program Certificates management command"""

from io import StringIO

import factory
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from courses.constants import PROGRAM_ENROLLMENT_UPGRADE_MODE
from courses.factories import (
    CourseFactory,
    CourseRunCertificateFactory,
    CourseRunFactory,
    CourseRunGradeFactory,
    EnrollmentModeFactory,
    ProgramCertificateFactory,
    ProgramFactory,
    ProgramRequirementFactory,  # noqa: F401
    program_with_empty_requirements,  # noqa: F401
    program_with_requirements,  # noqa: F401
)
from courses.management.commands import manage_program_certificates
from courses.models import ProgramCertificate, ProgramEnrollment
from openedx.constants import (
    EDX_ENROLLMENT_AUDIT_MODE,
    EDX_ENROLLMENT_VERIFIED_MODE,
)
from users.factories import UserFactory

pytestmark = [pytest.mark.django_db]


@pytest.fixture
def edx_grade_json(user):
    return {
        "passed": True,
        "course_id": "test_course_id",
        "username": user.edx_username,
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
            user=test_user.edx_username, create=True
        )
    assert (
        str(command_error.value) == f"Could not find program with readable_id={None}."
    )

    with pytest.raises(CommandError) as command_error:
        manage_program_certificates.Command().handle(
            user=test_user.edx_username, create=True, program="test"
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
        user=user.edx_username,
    )
    certificate.refresh_from_db()
    assert certificate.is_revoked is (True if revoke else False)  # noqa: SIM210
    assert certificate.is_revoked is (False if unrevoke else True)  # noqa: SIM211


@pytest.mark.parametrize(
    "force_cert",
    [
        True,
        False,
    ],
)
def test_program_certificate_management_create(
    user,
    program_with_empty_requirements,  # noqa: F811
    mocker,
    force_cert,
):
    """
    Test that create operation for program certificate management command
    creates the program certificate for a user
    """
    modes = [
        EnrollmentModeFactory.create(mode_slug=EDX_ENROLLMENT_AUDIT_MODE),
        EnrollmentModeFactory.create(mode_slug=EDX_ENROLLMENT_VERIFIED_MODE),
    ]

    ProgramEnrollment.objects.create(
        user=user,
        program=program_with_empty_requirements,
        enrollment_mode=PROGRAM_ENROLLMENT_UPGRADE_MODE,
    )

    mocker.patch(
        "hubspot_sync.api.upsert_custom_properties",
    )
    courses = CourseFactory.create_batch(2)
    program_with_empty_requirements.add_requirement(courses[0])
    program_with_empty_requirements.add_elective(courses[1])
    course_runs = CourseRunFactory.create_batch(2, course=factory.Iterator(courses))
    for run in course_runs:
        run.enrollment_modes.set(modes)
        run.save()
    CourseRunCertificateFactory.create_batch(
        2, user=user, course_run=factory.Iterator(course_runs)
    )
    manage_program_certificates.Command().handle(
        create=True,
        program=program_with_empty_requirements.readable_id,
        user=user.edx_username,
        force=force_cert,
    )

    generated_certificates = ProgramCertificate.objects.filter(
        user=user, program=program_with_empty_requirements
    )

    assert generated_certificates.count() == (1 if force_cert else 0)


def test_program_certificate_management_force_create(
    user,
    program_with_requirements,  # noqa: F811
    mocker,
):
    """
    Test that create operation for program certificate management command
    forcefully creates the certificate for a user
    """
    mocker.patch(
        "hubspot_sync.api.upsert_custom_properties",
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
        user=user.edx_username,
        force=True,
    )

    generated_certificates = ProgramCertificate.objects.filter(
        user=user, program=program_with_requirements.program
    )

    assert generated_certificates.count() == 1


def _program_needing(course):
    """A program whose only requirement is the given course."""
    program = ProgramFactory.create()
    program.add_requirement(course)
    return program


def _call_create(program, user=None, verbosity=1):
    out = StringIO()
    options = {"create": True, "program": program.readable_id, "verbosity": verbosity}
    if user is not None:
        options["user"] = user.edx_username
    call_command("manage_program_certificates", stdout=out, **options)
    return out.getvalue()


def test_program_certificate_management_create_lists_missing_requirements(user):
    """A user who hasn't met the requirements is told which ones are missing and why"""
    course = CourseFactory.create()
    program = _program_needing(course)
    ProgramEnrollment.objects.create(
        user=user, program=program, enrollment_mode=PROGRAM_ENROLLMENT_UPGRADE_MODE
    )

    output = _call_create(program, user=user)

    assert "Certificate: not created, program requirements are not met." in output
    assert "Use -f or --force" in output
    assert f"✗ {course.readable_id} {course.title}: not enrolled in any run" in output
    assert ProgramCertificate.objects.filter(user=user, program=program).count() == 0


def test_program_certificate_management_create_reports_skip_reason(user):
    """A skip that isn't about requirements says what it is"""
    program = _program_needing(CourseFactory.create())

    output = _call_create(program, user=user)

    assert "Certificate: not created, no active enrollment in the program." in output
    assert "Requirements:" not in output


@pytest.mark.parametrize("verbosity", [1, 2, 3])
def test_program_certificate_management_bulk_create_reports_skips(verbosity):
    """Bulk creation counts skips by reason and, with -v 2 or more, lists each user"""
    course = CourseFactory.create()
    program = _program_needing(course)
    audit_user, upgrade_user = UserFactory.create_batch(2)
    ProgramEnrollment.objects.create(
        user=audit_user, program=program, enrollment_mode=EDX_ENROLLMENT_AUDIT_MODE
    )
    ProgramEnrollment.objects.create(
        user=upgrade_user,
        program=program,
        enrollment_mode=PROGRAM_ENROLLMENT_UPGRADE_MODE,
    )

    output = _call_create(program, verbosity=verbosity)

    assert (
        f"Successfully created 0 certificates for program {program.readable_id}"
        in output
    )
    # The enrollment mode doesn't matter, so both users are skipped for the
    # same reason.
    assert "Skipped 2 user(s): program requirements are not met." in output
    listed = f"Skipped {upgrade_user.edx_username} ({upgrade_user.email})"
    missing = f"Missing: {course.readable_id} {course.title} (not enrolled in any run)"
    breakdown = f"✗ {course.readable_id} {course.title}: not enrolled in any run"
    assert (listed in output) is (verbosity >= 2)
    assert (missing in output) is (verbosity == 2)
    assert (breakdown in output) is (verbosity == 3)
    assert ("Run with -v 2" in output) is (verbosity == 1)
