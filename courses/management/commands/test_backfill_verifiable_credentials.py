"""Tests for the backfill_verifiable_credentials management command."""

from io import StringIO

import pytest
from django.core.management import call_command

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
