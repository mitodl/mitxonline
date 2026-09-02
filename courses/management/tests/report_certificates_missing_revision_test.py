"""Tests for report_certificates_missing_revision command."""

from io import StringIO

import pytest

from courses.factories import CourseRunCertificateFactory, ProgramCertificateFactory
from courses.management.commands import report_certificates_missing_revision

pytestmark = [pytest.mark.django_db]


@pytest.fixture(autouse=True)
def _mock_hubspot(mocker):
    mocker.patch("hubspot_sync.api.upsert_custom_properties")


def _run_command():
    out = StringIO()
    report_certificates_missing_revision.Command(stdout=out).handle()
    return out.getvalue()


def test_report_certificates_missing_revision_no_rows():
    """
    A well-formed database should report zero rows.

    certificate_page_revision is non-nullable at the DB level, so a "missing
    revision" row can't be constructed here the way it could pre-migration
    (see migrate_certificate_revisions_test.py, which predates the
    constraint) - this command's non-zero path is exercised against real
    pre-migration data during rollout, not in this test suite.
    """
    CourseRunCertificateFactory.create()
    ProgramCertificateFactory.create()

    output = _run_command()

    assert "CourseRunCertificates missing a revision: 0" in output
    assert "ProgramCertificates missing a revision: 0" in output
    assert "CourseRunCertificate details:" not in output
    assert "ProgramCertificate details:" not in output
