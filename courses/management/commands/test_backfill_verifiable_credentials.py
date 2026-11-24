"""Tests for the backfill_verifiable_credentials management command."""

from io import StringIO

import pytest
from django.core.management import call_command

from courses.factories import (
    CourseRunCertificateFactory,
    CourseRunFactory,
    ProgramCertificateFactory,
    ProgramFactory,
)

pytestmark = [pytest.mark.django_db]


def _signed(payload):
    return {**payload, "proof": {"type": "DataIntegrityProof"}}


@pytest.fixture
def signer(mocker):
    """Stand in for the signing service"""
    return mocker.patch(
        "courses.api.request_verifiable_credential", side_effect=_signed
    )


def _run(certificate, *extra_args):
    """Run the command and return everything it wrote to stdout and stderr"""
    out = StringIO()
    call_command(
        "backfill_verifiable_credentials",
        "--uuid",
        str(certificate.uuid),
        "--execute",
        *extra_args,
        stdout=out,
        stderr=out,
    )
    return out.getvalue()


def test_creates_missing_credential(signer, make_certificate, mock_certificate_page):
    """A certificate without a credential gets one"""
    mock_certificate_page()
    certificate = make_certificate(with_credential=False)

    output = _run(certificate)

    certificate.refresh_from_db()
    assert certificate.verifiable_credential.credential_data["proof"]
    assert "Backfilled" in output


def test_existing_credential_is_skipped_without_force(
    signer, make_certificate, mock_certificate_page
):
    """Without --force an existing credential is left alone"""
    mock_certificate_page()
    certificate = make_certificate()

    output = _run(certificate)

    signer.assert_not_called()
    certificate.refresh_from_db()
    assert certificate.verifiable_credential.credential_data["old"] is True
    assert "already has a verifiable credential" in output
    assert "Backfilled" not in output


def test_force_replaces_existing_credential(
    signer, make_certificate, mock_certificate_page
):
    """--force replaces an existing credential with a newly signed one"""
    mock_certificate_page()
    certificate = make_certificate()

    output = _run(certificate, "--force")

    certificate.refresh_from_db()
    assert "old" not in certificate.verifiable_credential.credential_data
    assert certificate.verifiable_credential.credential_data["proof"]
    assert "Backfilled" in output


def test_force_keeps_existing_credential_when_page_not_eligible(
    signer, make_certificate, mock_certificate_page
):
    """--force doesn't delete a credential it can't replace"""
    mock_certificate_page(eligible=False)
    certificate = make_certificate()

    output = _run(certificate, "--force")

    signer.assert_not_called()
    certificate.refresh_from_db()
    assert certificate.verifiable_credential.credential_data["old"] is True
    assert "skipped" in output
    assert "Backfilled" not in output


def test_force_keeps_existing_credential_when_signing_fails(
    signer, make_certificate, mock_certificate_page
):
    """--force reports the failure and doesn't delete a credential it couldn't replace"""
    mock_certificate_page()
    certificate = make_certificate()
    signer.side_effect = RuntimeError("signer down")

    output = _run(certificate, "--force")

    certificate.refresh_from_db()
    assert certificate.verifiable_credential.credential_data["old"] is True
    assert "Failed to backfill" in output
    assert "Backfilled" not in output


def test_force_creates_credential_when_certificate_has_none(
    signer, make_certificate, mock_certificate_page
):
    """--force on a certificate with no credential just creates one"""
    mock_certificate_page()
    certificate = make_certificate(with_credential=False)

    output = _run(certificate, "--force")

    certificate.refresh_from_db()
    assert certificate.verifiable_credential.credential_data["proof"]
    assert "Attempting to replace" not in output
    assert "Backfilled" in output


def test_dry_run_changes_nothing(signer, make_certificate, mock_certificate_page):
    """Without --execute the command only lists what it would process"""
    mock_certificate_page()
    certificate = make_certificate()
    out = StringIO()

    call_command(
        "backfill_verifiable_credentials",
        "--uuid",
        str(certificate.uuid),
        "--force",
        stdout=out,
        stderr=out,
    )

    signer.assert_not_called()
    certificate.refresh_from_db()
    assert certificate.verifiable_credential.credential_data["old"] is True
    assert "DRY RUN" in out.getvalue()
    assert "Backfilled" not in out.getvalue()


@pytest.fixture
def program_selection(mock_certificate_page):
    """Certificates for the program being backfilled, plus ones that must be left alone"""
    mock_certificate_page()
    program = ProgramFactory.create()
    return {
        "program": program,
        "targets": ProgramCertificateFactory.create_batch(2, program=program),
        "others": [
            ProgramCertificateFactory.create(),
            CourseRunCertificateFactory.create(),
        ],
    }


def _run_by_program(readable_id, *extra_args):
    out = StringIO()
    call_command(
        "backfill_verifiable_credentials",
        "--type",
        "program",
        "--ids",
        readable_id,
        *extra_args,
        stdout=out,
        stderr=out,
    )
    return out.getvalue()


def test_program_ids_backfills_only_that_programs_certificates(
    signer, program_selection
):
    """--type program --ids processes every certificate of the named program and no others"""
    _run_by_program(program_selection["program"].readable_id, "--execute")

    for certificate in program_selection["targets"]:
        certificate.refresh_from_db()
        assert certificate.verifiable_credential.credential_data["proof"]
    for certificate in program_selection["others"]:
        certificate.refresh_from_db()
        assert certificate.verifiable_credential is None
    assert signer.call_count == len(program_selection["targets"])


def test_program_ids_dry_run_changes_nothing(signer, program_selection):
    """Without --execute the program selection is only listed"""
    output = _run_by_program(program_selection["program"].readable_id)

    signer.assert_not_called()
    for certificate in program_selection["targets"]:
        certificate.refresh_from_db()
        assert certificate.verifiable_credential is None
        assert f"DRY RUN -- Would backfill certificate {certificate}" in output
    assert "Backfilled" not in output


def test_program_ids_with_no_matching_program_processes_nothing(
    signer, program_selection
):
    """An unknown program readable id selects no certificates"""
    output = _run_by_program("program-v1:does+not+exist", "--execute")

    signer.assert_not_called()
    assert "Backfilled" not in output
    assert "DRY RUN" not in output
    for certificate in program_selection["targets"] + program_selection["others"]:
        certificate.refresh_from_db()
        assert certificate.verifiable_credential is None


@pytest.fixture
def course_selection(mock_certificate_page):
    """Certificates for the course run being backfilled, plus ones that must be left alone"""
    mock_certificate_page()
    course_run = CourseRunFactory.create()
    return {
        "course_run": course_run,
        "targets": CourseRunCertificateFactory.create_batch(2, course_run=course_run),
        "others": [
            CourseRunCertificateFactory.create(),
            ProgramCertificateFactory.create(),
        ],
    }


def _run_by_course(courseware_id, *extra_args):
    out = StringIO()
    call_command(
        "backfill_verifiable_credentials",
        "--type",
        "course",
        "--ids",
        courseware_id,
        *extra_args,
        stdout=out,
        stderr=out,
    )
    return out.getvalue()


def test_course_ids_backfills_only_that_course_runs_certificates(
    signer, course_selection
):
    """--type course --ids processes every certificate of the named course run and no others"""
    _run_by_course(course_selection["course_run"].courseware_id, "--execute")

    for certificate in course_selection["targets"]:
        certificate.refresh_from_db()
        assert certificate.verifiable_credential.credential_data["proof"]
    for certificate in course_selection["others"]:
        certificate.refresh_from_db()
        assert certificate.verifiable_credential is None
    assert signer.call_count == len(course_selection["targets"])


def test_course_ids_dry_run_changes_nothing(signer, course_selection):
    """Without --execute the course run selection is only listed"""
    output = _run_by_course(course_selection["course_run"].courseware_id)

    signer.assert_not_called()
    for certificate in course_selection["targets"]:
        certificate.refresh_from_db()
        assert certificate.verifiable_credential is None
        assert f"DRY RUN -- Would backfill certificate {certificate}" in output
    assert "Backfilled" not in output


def test_course_ids_with_no_matching_course_run_processes_nothing(
    signer, course_selection
):
    """An unknown courseware id selects no certificates"""
    output = _run_by_course("course-v1:does+not+exist", "--execute")

    signer.assert_not_called()
    assert "Backfilled" not in output
    assert "DRY RUN" not in output
    for certificate in course_selection["targets"] + course_selection["others"]:
        certificate.refresh_from_db()
        assert certificate.verifiable_credential is None
