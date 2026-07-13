"""Tests for migrate_certificate_revisions management command"""

import pytest
from django.core.management.base import CommandError

from courses.factories import (
    CourseFactory,
    CourseRunCertificateFactory,
    CourseRunFactory,
    ProgramCertificateFactory,
    ProgramFactory,
)
from courses.management.commands import migrate_certificate_revisions
from courses.models import CourseRunCertificate, ProgramCertificate
from users.factories import UserFactory

pytestmark = [pytest.mark.django_db]


@pytest.fixture(autouse=True)
def _mock_hubspot(mocker):
    mocker.patch("hubspot_sync.api.upsert_custom_properties")


def _make_course_certs():
    """Create a course with one certificate that has a revision and one that doesn't"""
    course = CourseFactory.create(page__certificate_page__product_name="product")
    certificate_page = course.certificate_page
    # Establish an initial revision so the first certificate below picks one up.
    certificate_page.save_revision()

    run_a = CourseRunFactory.create(course=course)
    run_b = CourseRunFactory.create(course=course)
    cert_with_revision = CourseRunCertificateFactory.create(course_run=run_a)
    cert_without_revision = CourseRunCertificateFactory.create(course_run=run_b)
    CourseRunCertificate.all_objects.filter(pk=cert_without_revision.pk).update(
        certificate_page_revision=None
    )
    return (
        certificate_page,
        cert_with_revision,
        cert_without_revision,
        {"course": course.readable_id},
    )


def _make_course_run_certs():
    """Create a course run with one certificate that has a revision and one that doesn't"""
    course = CourseFactory.create(page__certificate_page__product_name="product")
    certificate_page = course.certificate_page
    # Establish an initial revision so the first certificate below picks one up.
    certificate_page.save_revision()

    run = CourseRunFactory.create(course=course)
    cert_with_revision = CourseRunCertificateFactory.create(
        course_run=run, user=UserFactory.create()
    )
    cert_without_revision = CourseRunCertificateFactory.create(
        course_run=run, user=UserFactory.create()
    )
    CourseRunCertificate.all_objects.filter(pk=cert_without_revision.pk).update(
        certificate_page_revision=None
    )
    return (
        certificate_page,
        cert_with_revision,
        cert_without_revision,
        {"courserun": run.courseware_id},
    )


def _make_program_certs():
    """Create a program with one certificate that has a revision and one that doesn't"""
    program = ProgramFactory.create(page__certificate_page__product_name="product")
    certificate_page = program.certificate_page
    # Establish an initial revision so the first certificate below picks one up.
    certificate_page.save_revision()

    cert_with_revision = ProgramCertificateFactory.create(
        program=program, user=UserFactory.create()
    )
    cert_without_revision = ProgramCertificateFactory.create(
        program=program, user=UserFactory.create()
    )
    ProgramCertificate.all_objects.filter(pk=cert_without_revision.pk).update(
        certificate_page_revision=None
    )
    return (
        certificate_page,
        cert_with_revision,
        cert_without_revision,
        {"program": program.readable_id},
    )


CERT_SETUPS = {
    "course": _make_course_certs,
    "courserun": _make_course_run_certs,
    "program": _make_program_certs,
}


@pytest.mark.parametrize(
    "handle_kwargs, expected_message",  # noqa: PT006
    [
        ({}, "The command needs one of --course, --courserun, or --program."),
        (
            {"course": "a", "program": "b"},
            "Provide only one of --course, --courserun, or --program.",
        ),
        (
            {"course": "a", "courserun": "b", "program": "c"},
            "Provide only one of --course, --courserun, or --program.",
        ),
        (
            {"course": "does-not-exist"},
            "Could not find course with readable_id=does-not-exist.",
        ),
        (
            {"courserun": "does-not-exist"},
            "Could not find course run with courseware_id=does-not-exist.",
        ),
        (
            {"program": "does-not-exist"},
            "Could not find program with readable_id=does-not-exist.",
        ),
    ],
)
def test_migrate_certificate_revisions_validation_errors(
    handle_kwargs, expected_message
):
    """Command should raise a CommandError for invalid/missing arguments"""
    with pytest.raises(CommandError) as command_error:
        migrate_certificate_revisions.Command().handle(**handle_kwargs)
    assert str(command_error.value) == expected_message


def test_migrate_certificate_revisions_course_no_certificate_page():
    """Command should fail if the course has no certificate page"""
    course = CourseFactory.create(page=None)
    with pytest.raises(CommandError) as command_error:
        migrate_certificate_revisions.Command().handle(course=course.readable_id)
    assert (
        str(command_error.value)
        == f"No certificate page found for course {course.readable_id}."
    )


@pytest.mark.parametrize("kind", ["course", "courserun", "program"])
def test_migrate_certificate_revisions_missing_only(kind):
    """By default, only certificates missing a revision should be updated"""
    certificate_page, cert_with_revision, cert_without_revision, handle_kwargs = (
        CERT_SETUPS[kind]()
    )
    old_revision = cert_with_revision.certificate_page_revision
    new_revision = certificate_page.save_revision()

    migrate_certificate_revisions.Command().handle(**handle_kwargs)

    cert_with_revision.refresh_from_db()
    cert_without_revision.refresh_from_db()

    assert old_revision is not None
    assert cert_with_revision.certificate_page_revision == old_revision
    assert cert_without_revision.certificate_page_revision == new_revision


@pytest.mark.parametrize("kind", ["course", "courserun", "program"])
@pytest.mark.parametrize("confirm_answer", ["y", "Y", "n", ""])
def test_migrate_certificate_revisions_all_confirmation(mocker, kind, confirm_answer):
    """--all should prompt for confirmation and only update when the user accepts"""
    certificate_page, cert_with_revision, cert_without_revision, handle_kwargs = (
        CERT_SETUPS[kind]()
    )
    old_revision = cert_with_revision.certificate_page_revision
    new_revision = certificate_page.save_revision()

    mock_input = mocker.patch("builtins.input", return_value=confirm_answer)

    migrate_certificate_revisions.Command().handle(update_all=True, **handle_kwargs)

    mock_input.assert_called_once()
    cert_with_revision.refresh_from_db()
    cert_without_revision.refresh_from_db()

    if confirm_answer.lower() == "y":
        assert cert_with_revision.certificate_page_revision == new_revision
        assert cert_without_revision.certificate_page_revision == new_revision
    else:
        assert cert_with_revision.certificate_page_revision == old_revision
        assert cert_without_revision.certificate_page_revision is None
