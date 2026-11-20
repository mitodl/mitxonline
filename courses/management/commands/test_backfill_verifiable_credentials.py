"""Tests for the backfill_verifiable_credentials management command."""

from io import StringIO
from unittest.mock import Mock

import pytest
from django.core.management import call_command

from courses.factories import CourseRunCertificateFactory
from courses.models import VerifiableCredential

pytestmark = [pytest.mark.django_db]


def _signed(payload):
    return {**payload, "proof": {"type": "DataIntegrityProof"}}


@pytest.fixture
def signer(mocker):
    """Stand in for the signing service"""
    return mocker.patch(
        "courses.api.request_verifiable_credential", side_effect=_signed
    )


def _set_certificate_page(mocker, *, eligible):
    certificate_page = Mock()
    certificate_page.verifiable_credential_criteria = "criteria" if eligible else ""
    certificate_page.should_provision_verifiable_credential = eligible
    mocker.patch("courses.api.get_certificate_page", return_value=certificate_page)
    mocker.patch(
        "courses.api.get_verifiable_credentials_payload",
        side_effect=lambda certificate, _page: {"id": f"urn:uuid:{certificate.uuid}"},
    )


def _certificate(*, with_credential):
    certificate = CourseRunCertificateFactory.create()
    if with_credential:
        certificate.verifiable_credential = VerifiableCredential.objects.create(
            uuid=certificate.uuid,
            credential_data={"id": f"urn:uuid:{certificate.uuid}", "old": True},
        )
        certificate.save()
    return certificate


def _run(certificate, *extra_args):
    out = StringIO()
    call_command(
        "backfill_verifiable_credentials",
        "--uuid",
        str(certificate.uuid),
        "--execute",
        *extra_args,
        stdout=out,
    )
    return out.getvalue()


def test_creates_missing_credential(mocker, signer):
    """A certificate without a credential gets one"""
    _set_certificate_page(mocker, eligible=True)
    certificate = _certificate(with_credential=False)

    output = _run(certificate)

    certificate.refresh_from_db()
    assert certificate.verifiable_credential.credential_data["proof"]
    assert "Backfilled" in output


def test_existing_credential_is_skipped_without_force(mocker, signer):
    """Without --force an existing credential is left alone"""
    _set_certificate_page(mocker, eligible=True)
    certificate = _certificate(with_credential=True)

    output = _run(certificate)

    signer.assert_not_called()
    certificate.refresh_from_db()
    assert certificate.verifiable_credential.credential_data["old"] is True
    assert "already has a verifiable credential" in output
    assert "Backfilled" not in output


def test_force_replaces_existing_credential(mocker, signer):
    """--force replaces an existing credential with a newly signed one"""
    _set_certificate_page(mocker, eligible=True)
    certificate = _certificate(with_credential=True)

    output = _run(certificate, "--force")

    certificate.refresh_from_db()
    assert "old" not in certificate.verifiable_credential.credential_data
    assert certificate.verifiable_credential.credential_data["proof"]
    assert "Backfilled" in output


def test_force_keeps_existing_credential_when_page_not_eligible(mocker, signer):
    """--force doesn't delete a credential it can't replace"""
    _set_certificate_page(mocker, eligible=False)
    certificate = _certificate(with_credential=True)

    output = _run(certificate, "--force")

    signer.assert_not_called()
    certificate.refresh_from_db()
    assert certificate.verifiable_credential.credential_data["old"] is True
    assert "skipped" in output
    assert "Backfilled" not in output
