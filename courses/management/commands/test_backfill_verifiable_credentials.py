"""Tests for the backfill_verifiable_credentials management command."""

from io import StringIO

import pytest
from django.core.management import call_command

from courses.factories import (
    CourseRunCertificateFactory,
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


def _call(*args):
    """Run the command and return everything it wrote to stdout and stderr"""
    out = StringIO()
    call_command("backfill_verifiable_credentials", *args, stdout=out, stderr=out)
    return out.getvalue()


def _run(certificate, *extra_args):
    """Execute the command for one certificate, selected by uuid"""
    return _call("--uuid", str(certificate.uuid), "--execute", *extra_args)


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

    output = _call("--uuid", str(certificate.uuid), "--force")

    signer.assert_not_called()
    certificate.refresh_from_db()
    assert certificate.verifiable_credential.credential_data["old"] is True
    assert "DRY RUN" in output
    assert "Backfilled" not in output


@pytest.fixture
def program_selection():
    """Certificates for the program being backfilled, plus ones that must be left alone"""
    program = ProgramFactory.create()
    return {
        "program": program,
        "targets": ProgramCertificateFactory.create_batch(2, program=program),
        "others": [
            ProgramCertificateFactory.create(),
            CourseRunCertificateFactory.create(),
        ],
    }


def _run_by_program(*readable_ids, execute=False):
    args = ["--type", "program", "--ids", ",".join(readable_ids)]
    return _call(*args, "--execute") if execute else _call(*args)


def test_program_ids_backfills_only_that_programs_certificates(
    signer, mock_certificate_page, program_selection
):
    """--type program --ids processes every certificate of the named program and no others"""
    mock_certificate_page()

    _run_by_program(program_selection["program"].readable_id, execute=True)

    for certificate in program_selection["targets"]:
        certificate.refresh_from_db()
        assert certificate.verifiable_credential.credential_data["proof"]
    for certificate in program_selection["others"]:
        certificate.refresh_from_db()
        assert certificate.verifiable_credential is None
    assert signer.call_count == len(program_selection["targets"])


def test_program_ids_accepts_several_programs(
    signer, mock_certificate_page, program_selection
):
    """A comma-separated --ids list selects the certificates of every program in it"""
    mock_certificate_page()
    other_program_certificate, course_run_certificate = program_selection["others"]

    _run_by_program(
        program_selection["program"].readable_id,
        other_program_certificate.program.readable_id,
        execute=True,
    )

    for certificate in [*program_selection["targets"], other_program_certificate]:
        certificate.refresh_from_db()
        assert certificate.verifiable_credential.credential_data["proof"]
    course_run_certificate.refresh_from_db()
    assert course_run_certificate.verifiable_credential is None
    assert signer.call_count == len(program_selection["targets"]) + 1


def test_program_ids_dry_run_lists_but_does_not_change_certificates(
    signer, program_selection
):
    """Without --execute the named program's certificates are listed, not changed, and no others are listed"""
    output = _run_by_program(program_selection["program"].readable_id)

    signer.assert_not_called()
    for certificate in program_selection["targets"]:
        certificate.refresh_from_db()
        assert certificate.verifiable_credential is None
        assert f"DRY RUN -- Would backfill certificate {certificate}" in output
    for certificate in program_selection["others"]:
        assert str(certificate) not in output
    assert "Backfilled" not in output


def test_program_ids_with_no_matching_program_processes_nothing(
    signer, program_selection
):
    """An unknown program readable id selects no certificates"""
    output = _run_by_program("program-v1:does+not+exist", execute=True)

    signer.assert_not_called()
    assert output == ""
    for certificate in program_selection["targets"] + program_selection["others"]:
        certificate.refresh_from_db()
        assert certificate.verifiable_credential is None
