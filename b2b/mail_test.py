"""Tests for B2B mail."""

import uuid
from unittest.mock import MagicMock

import pytest
from anymail.message import AnymailRecipientStatus, AnymailStatus
from django.test import override_settings

from b2b.mail import EnrollmentCodeAssignmentMessage, send_email_helper

pytestmark = [pytest.mark.django_db]

EMAIL = "learner@example.com"
CODE = "SOMECODE"
CODE_URL = "https://learn.mit.edu/enrollmentcode/SOMECODE"
ORGANIZATION_NAME = "Test Org"
CONTRACT_NAME = "Test Contract"

MAILGUN_BACKEND = "anymail.backends.mailgun.EmailBackend"
SMTP_BACKEND = "django.core.mail.backends.smtp.EmailBackend"


def make_fake_message(mocker, message_id=None, send_side_effect=None):
    """
    Bypass real message construction (template rendering/premailer) by patching
    EnrollmentCodeAssignmentMessage.create to hand back a fake message object we
    control directly, with anymail_status pre-populated as if already sent.
    """
    message = MagicMock()
    message.anymail_status = AnymailStatus()
    if message_id is not None:
        message.anymail_status.set_recipient_status(
            {EMAIL: AnymailRecipientStatus(message_id=message_id, status="queued")}
        )
    if send_side_effect is not None:
        message.send.side_effect = send_side_effect
    mocker.patch.object(EnrollmentCodeAssignmentMessage, "create", return_value=message)
    return message


@override_settings(MITOL_MAIL_CONNECTION_BACKEND=MAILGUN_BACKEND)
def test_send_email_helper_returns_mailgun_message_id(mocker):
    """When using the mailgun backend, the mailgun message id should be returned."""
    make_fake_message(mocker, message_id="mailgun-message-id-123")

    message_id = send_email_helper(
        EMAIL, CODE, CODE_URL, ORGANIZATION_NAME, CONTRACT_NAME
    )

    assert message_id == "mailgun-message-id-123"


@override_settings(MITOL_MAIL_CONNECTION_BACKEND=MAILGUN_BACKEND)
def test_send_email_helper_returns_none_when_mailgun_status_missing(mocker):
    """
    If the mailgun backend is configured but no recipient status ends up on the
    message (e.g. the send didn't populate it), we should get None back rather
    than raising.
    """
    make_fake_message(mocker)

    message_id = send_email_helper(
        EMAIL, CODE, CODE_URL, ORGANIZATION_NAME, CONTRACT_NAME
    )

    assert message_id is None


@override_settings(MITOL_MAIL_CONNECTION_BACKEND=SMTP_BACKEND)
def test_send_email_helper_returns_uuid_for_non_mailgun_backend(mocker):
    """When not using the mailgun backend (e.g. local SMTP), a UUID should be generated instead."""
    make_fake_message(mocker)

    message_id = send_email_helper(
        EMAIL, CODE, CODE_URL, ORGANIZATION_NAME, CONTRACT_NAME
    )

    assert message_id is not None
    assert uuid.UUID(message_id, version=4)


@override_settings(MITOL_MAIL_CONNECTION_BACKEND=SMTP_BACKEND)
def test_send_email_helper_generates_unique_uuids_for_non_mailgun_backend(mocker):
    """Each send on a non-mailgun backend should get its own unique fallback id."""
    make_fake_message(mocker)

    first_id = send_email_helper(
        EMAIL, CODE, CODE_URL, ORGANIZATION_NAME, CONTRACT_NAME
    )
    second_id = send_email_helper(
        EMAIL, CODE, CODE_URL, ORGANIZATION_NAME, CONTRACT_NAME
    )

    assert first_id != second_id


@override_settings(MITOL_MAIL_CONNECTION_BACKEND=SMTP_BACKEND)
def test_send_email_helper_ignores_mailgun_status_on_non_mailgun_backend(mocker):
    """
    Even if anymail_status happens to be populated (e.g. leftover from a prior
    send), a non-mailgun backend should still return a generated UUID rather
    than the mailgun message id.
    """
    make_fake_message(mocker, message_id="mailgun-message-id-should-be-ignored")

    message_id = send_email_helper(
        EMAIL, CODE, CODE_URL, ORGANIZATION_NAME, CONTRACT_NAME
    )

    assert message_id != "mailgun-message-id-should-be-ignored"
    assert uuid.UUID(message_id, version=4)


@override_settings(MITOL_MAIL_CONNECTION_BACKEND=MAILGUN_BACKEND)
def test_send_email_helper_logs_and_returns_none_on_send_error(mocker):
    """If sending raises, the exception should be logged and swallowed, returning None."""
    make_fake_message(mocker, send_side_effect=ConnectionError("boom"))
    patched_logger = mocker.patch("b2b.mail.log")

    message_id = send_email_helper(
        EMAIL, CODE, CODE_URL, ORGANIZATION_NAME, CONTRACT_NAME
    )

    assert message_id is None
    patched_logger.exception.assert_called_once()
