"""Tests for migrate_certificate_revisions management command"""

from io import StringIO

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
from users.factories import UserFactory

pytestmark = [pytest.mark.django_db]


@pytest.fixture(autouse=True)
def _mock_hubspot(mocker):
    mocker.patch("hubspot_sync.api.upsert_custom_properties")


def _make_course_cert():
    """Create a course with one certificate (which always has a revision)"""
    course = CourseFactory.create(page__certificate_page__product_name="product")
    certificate_page = course.certificate_page
    run = CourseRunFactory.create(course=course)
    cert = CourseRunCertificateFactory.create(course_run=run)
    return certificate_page, cert, {"course": course.readable_id}


def _make_course_run_cert():
    """Create a course run with one certificate"""
    course = CourseFactory.create(page__certificate_page__product_name="product")
    certificate_page = course.certificate_page
    run = CourseRunFactory.create(course=course)
    cert = CourseRunCertificateFactory.create(
        course_run=run, user=UserFactory.create()
    )
    return certificate_page, cert, {"courserun": run.courseware_id}


def _make_program_cert():
    """Create a program with one certificate"""
    program = ProgramFactory.create(page__certificate_page__product_name="product")
    certificate_page = program.certificate_page
    cert = ProgramCertificateFactory.create(
        program=program, user=UserFactory.create()
    )
    return certificate_page, cert, {"program": program.readable_id}


CERT_SETUPS = {
    "course": _make_course_cert,
    "courserun": _make_course_run_cert,
    "program": _make_program_cert,
}


def _run_all_missing():
    out = StringIO()
    migrate_certificate_revisions.Command(stdout=out).handle(all_missing=True)
    return out.getvalue()


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


@pytest.mark.parametrize(
    "handle_kwargs",
    [
        {"all_missing": True, "course": "a"},
        {"all_missing": True, "courserun": "a"},
        {"all_missing": True, "program": "a"},
        {"all_missing": True, "update_all": True},
    ],
)
def test_migrate_certificate_revisions_all_missing_rejects_other_flags(handle_kwargs):
    """--all-missing can't be combined with --course/--courserun/--program/--all"""
    with pytest.raises(CommandError) as command_error:
        migrate_certificate_revisions.Command().handle(**handle_kwargs)
    assert "--all-missing cannot be combined with" in str(command_error.value)


def test_migrate_certificate_revisions_course_no_certificate_page():
    """Command should fail if the course has no certificate page"""
    course = CourseFactory.create(page=None)
    with pytest.raises(CommandError) as command_error:
        migrate_certificate_revisions.Command().handle(course=course.readable_id)
    assert (
        str(command_error.value)
        == f"No certificate page found for course {course.readable_id}."
    )


def test_migrate_certificate_revisions_certificate_page_has_no_revisions():
    """Command should fail if the certificate page exists but has no revisions."""
    course = CourseFactory.create(page__certificate_page__product_name="product")
    certificate_page = course.certificate_page
    certificate_page.revisions.all().delete()

    with pytest.raises(CommandError) as command_error:
        migrate_certificate_revisions.Command().handle(course=course.readable_id)

    assert f"course {course.readable_id}" in str(command_error.value)
    assert "has no revisions" in str(command_error.value)


@pytest.mark.parametrize("kind", ["course", "courserun", "program"])
def test_migrate_certificate_revisions_missing_only_leaves_existing_untouched(kind):
    """By default, certificates that already have a revision are left untouched"""
    certificate_page, cert, handle_kwargs = CERT_SETUPS[kind]()
    old_revision = cert.certificate_page_revision
    # A newer revision now exists on the page, but the cert isn't "missing" a
    # revision, so the default (non --all) mode shouldn't touch it.
    certificate_page.save_revision()

    migrate_certificate_revisions.Command().handle(**handle_kwargs)

    cert.refresh_from_db()
    assert old_revision is not None
    assert cert.certificate_page_revision == old_revision


@pytest.mark.parametrize("kind", ["course", "courserun", "program"])
@pytest.mark.parametrize("confirm_answer", ["y", "Y", "n", ""])
def test_migrate_certificate_revisions_all_confirmation(mocker, kind, confirm_answer):
    """--all should prompt for confirmation and only update when the user accepts"""
    certificate_page, cert, handle_kwargs = CERT_SETUPS[kind]()
    old_revision = cert.certificate_page_revision
    new_revision = certificate_page.save_revision()

    mock_input = mocker.patch("builtins.input", return_value=confirm_answer)

    migrate_certificate_revisions.Command().handle(update_all=True, **handle_kwargs)

    mock_input.assert_called_once()
    cert.refresh_from_db()

    if confirm_answer.lower() == "y":
        assert cert.certificate_page_revision == new_revision
    else:
        assert cert.certificate_page_revision == old_revision


def test_migrate_certificate_revisions_all_missing_is_a_noop_when_nothing_is_missing():
    """
    --all-missing shouldn't touch certificates that already have a revision.

    certificate_page_revision is non-nullable, so a "missing revision" row
    can't actually be constructed in a fully-migrated database - this just
    confirms the bulk pass leaves well-formed data alone.
    """
    _certificate_page, cert, _handle_kwargs = _make_course_cert()
    old_revision = cert.certificate_page_revision

    output = _run_all_missing()

    cert.refresh_from_db()
    assert cert.certificate_page_revision == old_revision
    assert "Updated 0 certificate(s) in total." in output


def test_migrate_certificate_revisions_all_missing_reports_pages_without_revisions():
    """--all-missing should report, not crash on, certificate pages with no revisions"""
    course = CourseFactory.create(page__certificate_page__product_name="product")
    course.certificate_page.revisions.all().delete()

    program = ProgramFactory.create(page__certificate_page__product_name="product")
    program.certificate_page.revisions.all().delete()

    output = _run_all_missing()

    assert f"Skipping course {course.readable_id}" in output
    assert f"Skipping program {program.readable_id}" in output
    assert "has no revisions" in output
