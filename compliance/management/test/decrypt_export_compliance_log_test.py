"""Tests for the decrypt_export_compliance_log management command."""

from io import StringIO

import pytest
from django.core.management import CommandError, call_command
from nacl.encoding import Base64Encoder

from compliance.api import ExportComplianceResult, log_export_compliance_check
from courses.factories import CourseRunFactory
from users.factories import UserFactory

pytestmark = [pytest.mark.django_db]


def test_decrypt_export_compliance_log(mocker, export_compliance_keypair):
    """The command should decrypt and print the latest logged request/response for a user."""
    user = UserFactory.create()
    run = CourseRunFactory.create()
    response = {"status": "COMPLETED", "id": "abc123"}
    result = ExportComplianceResult(
        decision="COMPLETED", reason_code=None, request_id="abc123", raw=response
    )
    log_export_compliance_check(user, run, '{"hello": "world"}', response, result)

    encoded_private_key = Base64Encoder.encode(bytes(export_compliance_keypair)).decode(
        "ascii"
    )
    mocker.patch("builtins.input", return_value=encoded_private_key)

    out = StringIO()
    call_command("decrypt_export_compliance_log", f"--user-id={user.id}", stdout=out)

    output = out.getvalue()
    assert '{"hello": "world"}' in output
    assert '"status": "COMPLETED"' in output


def test_decrypt_export_compliance_log_missing_user():
    """The command should raise a clear error when the user doesn't exist."""
    with pytest.raises(CommandError, match="User doesn't exist"):
        call_command("decrypt_export_compliance_log", "--user-id=0")


def test_decrypt_export_compliance_log_no_records():
    """The command should raise a clear error when the user has no logged checks."""
    user = UserFactory.create()
    with pytest.raises(CommandError, match="no ExportComplianceLog records"):
        call_command("decrypt_export_compliance_log", f"--user-id={user.id}")
