"""Tests for Mailgun webhook processing functions in b2b.api."""

# ruff: noqa: S105, S106 -- hardcoded test tokens/secrets, not real credentials

import hashlib
import hmac

import pytest
from django.test import override_settings

from b2b.api import (
    is_potentially_valid_mailgun_webhook,
    process_mailgun_webhook_for_enrollment_code_emails,
    verify_mailgun_signature,
)
from b2b.factories import ContractPageFactory
from b2b.mail import ENROLLMENT_CODE_ASSINGMENT_TAG
from b2b.models import (
    EMAIL_STATUS_ACCEPTED,
    EMAIL_STATUS_CLICKED,
    EMAIL_STATUS_DELIVERED,
    EMAIL_STATUS_FAILED,
    EMAIL_STATUS_FAILED_TEMPORARY_SEVERITY,
    EMAIL_STATUS_OPENED,
    DiscountContractAttachmentRedemption,
)
from ecommerce.factories import DiscountFactory

pytestmark = [pytest.mark.django_db]

SIGNING_SECRET = "test-signing-secret"
TOKEN = "some-token"
TIMESTAMP = "1700000000.0"


def _valid_signature(signing_secret=SIGNING_SECRET, token=TOKEN, timestamp=TIMESTAMP):
    message = f"{timestamp}{token}"
    return hmac.new(
        key=signing_secret.encode(), msg=message.encode(), digestmod=hashlib.sha256
    ).hexdigest()


def _build_payload(  # noqa: PLR0913
    *,
    event_type=EMAIL_STATUS_DELIVERED,
    message_id="message-id-1",
    tags=(ENROLLMENT_CODE_ASSINGMENT_TAG,),
    token=TOKEN,
    timestamp=TIMESTAMP,
    event_timestamp=1700000000.0,
    signature=None,
    signing_secret=SIGNING_SECRET,
    severity=None,
):
    """Build a Mailgun-shaped webhook payload for tests."""

    event_data = {
        "event": event_type,
        "tags": list(tags),
        "message": {"headers": {"message-id": message_id}},
        "timestamp": event_timestamp,
    }
    if severity is not None:
        event_data["severity"] = severity

    return {
        "signature": {
            "token": token,
            "timestamp": timestamp,
            "signature": (
                signature
                if signature is not None
                else _valid_signature(signing_secret, token, timestamp)
            ),
        },
        "event-data": event_data,
    }


class TestVerifyMailgunSignature:
    @override_settings(MAILGUN_WEBHOOK_VALIDATE_SIGNATURE=False)
    def test_returns_true_when_validation_disabled(self):
        """Signature checking should be skipped entirely when disabled, even if bogus."""
        assert (
            verify_mailgun_signature(
                SIGNING_SECRET, TOKEN, TIMESTAMP, "not-a-signature"
            )
            is True
        )

    @override_settings(MAILGUN_WEBHOOK_VALIDATE_SIGNATURE=True)
    def test_returns_true_for_matching_signature(self):
        signature = _valid_signature()
        assert (
            verify_mailgun_signature(SIGNING_SECRET, TOKEN, TIMESTAMP, signature)
            is True
        )

    @override_settings(MAILGUN_WEBHOOK_VALIDATE_SIGNATURE=True)
    def test_returns_false_for_mismatched_signature(self):
        assert (
            verify_mailgun_signature(
                SIGNING_SECRET, TOKEN, TIMESTAMP, "wrong-signature"
            )
            is False
        )

    @override_settings(MAILGUN_WEBHOOK_VALIDATE_SIGNATURE=True)
    def test_returns_false_when_token_differs(self):
        """A signature computed for a different token should not validate."""
        signature = _valid_signature(token="a-different-token")
        assert (
            verify_mailgun_signature(SIGNING_SECRET, TOKEN, TIMESTAMP, signature)
            is False
        )


class TestIsPotentiallyValidMailgunWebhook:
    @override_settings(
        MAILGUN_WEBHOOK_VALIDATE_SIGNATURE=True, MAILGUN_WEBHOOK_SIGNING_SECRET=""
    )
    def test_fails_closed_when_validation_enabled_but_no_secret_configured(self):
        """If we require validation but have no secret, treat everything as invalid."""
        payload = _build_payload()
        assert is_potentially_valid_mailgun_webhook(payload) is False

    @override_settings(
        MAILGUN_WEBHOOK_VALIDATE_SIGNATURE=False, MAILGUN_WEBHOOK_SIGNING_SECRET=""
    )
    def test_missing_secret_ok_when_validation_disabled(self):
        """No secret is fine as long as we aren't validating signatures."""
        payload = _build_payload()
        assert is_potentially_valid_mailgun_webhook(payload) is True

    @override_settings(
        MAILGUN_WEBHOOK_VALIDATE_SIGNATURE=False,
        MAILGUN_WEBHOOK_SIGNING_SECRET=SIGNING_SECRET,
    )
    def test_rejects_non_dict_payload(self):
        assert is_potentially_valid_mailgun_webhook(None) is False
        assert is_potentially_valid_mailgun_webhook([]) is False
        assert is_potentially_valid_mailgun_webhook("a string") is False

    @override_settings(
        MAILGUN_WEBHOOK_VALIDATE_SIGNATURE=False,
        MAILGUN_WEBHOOK_SIGNING_SECRET=SIGNING_SECRET,
    )
    def test_rejects_payload_with_no_event_data(self):
        assert is_potentially_valid_mailgun_webhook({}) is False

    @override_settings(
        MAILGUN_WEBHOOK_VALIDATE_SIGNATURE=False,
        MAILGUN_WEBHOOK_SIGNING_SECRET=SIGNING_SECRET,
    )
    def test_rejects_payload_missing_relevant_tag(self):
        payload = _build_payload(tags=("some-other-tag",))
        assert is_potentially_valid_mailgun_webhook(payload) is False

    @override_settings(
        MAILGUN_WEBHOOK_VALIDATE_SIGNATURE=False,
        MAILGUN_WEBHOOK_SIGNING_SECRET=SIGNING_SECRET,
    )
    def test_accepts_payload_with_relevant_tag(self):
        payload = _build_payload(tags=(ENROLLMENT_CODE_ASSINGMENT_TAG, "another-tag"))
        assert is_potentially_valid_mailgun_webhook(payload) is True


@pytest.fixture
def assignment():
    contract = ContractPageFactory.create()
    discount = DiscountFactory.create()
    return DiscountContractAttachmentRedemption.objects.create(
        discount=discount,
        contract=contract,
        assigned_email="learner@example.com",
        email_message_id="message-id-1",
    )


class TestProcessMailgunWebhookForEnrollmentCodeEmails:
    @override_settings(
        MAILGUN_WEBHOOK_VALIDATE_SIGNATURE=True,
        MAILGUN_WEBHOOK_SIGNING_SECRET=SIGNING_SECRET,
    )
    def test_returns_none_for_invalid_payload(self, assignment):  # noqa: ARG002
        """Payload missing the relevant tag should short-circuit with no result."""
        payload = _build_payload(tags=("unrelated-tag",))
        assert process_mailgun_webhook_for_enrollment_code_emails(payload) is None

    @override_settings(
        MAILGUN_WEBHOOK_VALIDATE_SIGNATURE=True,
        MAILGUN_WEBHOOK_SIGNING_SECRET=SIGNING_SECRET,
    )
    def test_returns_none_when_signature_invalid(self, assignment):  # noqa: ARG002
        payload = _build_payload(signature="totally-wrong-signature")
        assert process_mailgun_webhook_for_enrollment_code_emails(payload) is None

    @override_settings(
        MAILGUN_WEBHOOK_VALIDATE_SIGNATURE=True,
        MAILGUN_WEBHOOK_SIGNING_SECRET=SIGNING_SECRET,
    )
    def test_returns_none_for_uninteresting_event_type(self, assignment):  # noqa: ARG002
        payload = _build_payload(event_type="unsubscribed")
        assert process_mailgun_webhook_for_enrollment_code_emails(payload) is None

    @override_settings(
        MAILGUN_WEBHOOK_VALIDATE_SIGNATURE=True,
        MAILGUN_WEBHOOK_SIGNING_SECRET=SIGNING_SECRET,
    )
    @pytest.mark.parametrize(
        "event_type",
        [
            EMAIL_STATUS_DELIVERED,
            EMAIL_STATUS_ACCEPTED,
            EMAIL_STATUS_OPENED,
            EMAIL_STATUS_CLICKED,
        ],
    )
    def test_updates_matching_assignment_for_tracked_event_types(
        self, assignment, event_type
    ):
        payload = _build_payload(
            event_type=event_type, message_id=assignment.email_message_id
        )

        result = process_mailgun_webhook_for_enrollment_code_emails(payload)

        assert result == assignment
        assignment.refresh_from_db()
        assert assignment.email_status == event_type
        assert assignment.email_status_event_timestamp is not None

    @override_settings(
        MAILGUN_WEBHOOK_VALIDATE_SIGNATURE=True,
        MAILGUN_WEBHOOK_SIGNING_SECRET=SIGNING_SECRET,
    )
    def test_returns_none_for_temporary_failure(self, assignment):
        """Temporary failures should be filtered out and leave the assignment untouched."""
        payload = _build_payload(
            event_type=EMAIL_STATUS_FAILED,
            message_id=assignment.email_message_id,
            severity=EMAIL_STATUS_FAILED_TEMPORARY_SEVERITY,
        )

        assert process_mailgun_webhook_for_enrollment_code_emails(payload) is None
        assignment.refresh_from_db()
        assert assignment.email_status == ""
        assert assignment.email_status_event_timestamp is None

    @override_settings(
        MAILGUN_WEBHOOK_VALIDATE_SIGNATURE=True,
        MAILGUN_WEBHOOK_SIGNING_SECRET=SIGNING_SECRET,
    )
    def test_updates_matching_assignment_for_permanent_failure(self, assignment):
        """Permanent failures are the ones contract managers should actually see."""
        payload = _build_payload(
            event_type=EMAIL_STATUS_FAILED,
            message_id=assignment.email_message_id,
            severity="permanent",
        )

        result = process_mailgun_webhook_for_enrollment_code_emails(payload)

        assert result == assignment
        assignment.refresh_from_db()
        assert assignment.email_status == EMAIL_STATUS_FAILED
        assert assignment.email_status_event_timestamp is not None

    @override_settings(
        MAILGUN_WEBHOOK_VALIDATE_SIGNATURE=True,
        MAILGUN_WEBHOOK_SIGNING_SECRET=SIGNING_SECRET,
    )
    def test_raises_when_no_assignment_matches_message_id(self, assignment):  # noqa: ARG002
        """
        There's no record with this message ID, so the lookup should raise.
        This isn't handled specially - it's expected to surface as a task failure.
        """
        payload = _build_payload(message_id="some-unknown-message-id")

        with pytest.raises(DiscountContractAttachmentRedemption.DoesNotExist):
            process_mailgun_webhook_for_enrollment_code_emails(payload)


class TestProcessMailgunWebhookEventOrdering:
    """Mailgun doesn't guarantee events arrive in the order they occurred, so
    a later-arriving event with an earlier timestamp shouldn't clobber a
    status that came from an event which occurred more recently.
    """

    @override_settings(
        MAILGUN_WEBHOOK_VALIDATE_SIGNATURE=True,
        MAILGUN_WEBHOOK_SIGNING_SECRET=SIGNING_SECRET,
    )
    def test_newer_event_updates_status(self, assignment):
        first = _build_payload(
            event_type=EMAIL_STATUS_DELIVERED,
            message_id=assignment.email_message_id,
            event_timestamp=1000.0,
        )
        process_mailgun_webhook_for_enrollment_code_emails(first)
        assignment.refresh_from_db()
        first_timestamp = assignment.email_status_event_timestamp

        second = _build_payload(
            event_type=EMAIL_STATUS_OPENED,
            message_id=assignment.email_message_id,
            event_timestamp=2000.0,
        )
        result = process_mailgun_webhook_for_enrollment_code_emails(second)

        assert result == assignment
        assignment.refresh_from_db()
        assert assignment.email_status == EMAIL_STATUS_OPENED
        assert assignment.email_status_event_timestamp > first_timestamp

    @override_settings(
        MAILGUN_WEBHOOK_VALIDATE_SIGNATURE=True,
        MAILGUN_WEBHOOK_SIGNING_SECRET=SIGNING_SECRET,
    )
    def test_older_event_does_not_clobber_status(self, assignment):
        first = _build_payload(
            event_type=EMAIL_STATUS_OPENED,
            message_id=assignment.email_message_id,
            event_timestamp=2000.0,
        )
        process_mailgun_webhook_for_enrollment_code_emails(first)
        assignment.refresh_from_db()
        first_timestamp = assignment.email_status_event_timestamp

        second = _build_payload(
            event_type=EMAIL_STATUS_DELIVERED,
            message_id=assignment.email_message_id,
            event_timestamp=1000.0,
        )
        result = process_mailgun_webhook_for_enrollment_code_emails(second)

        assert result == assignment
        assignment.refresh_from_db()
        assert assignment.email_status == EMAIL_STATUS_OPENED
        assert assignment.email_status_event_timestamp == first_timestamp

    @override_settings(
        MAILGUN_WEBHOOK_VALIDATE_SIGNATURE=True,
        MAILGUN_WEBHOOK_SIGNING_SECRET=SIGNING_SECRET,
    )
    def test_event_with_same_timestamp_does_not_reapply(self, assignment):
        """A duplicate/replayed event at the same timestamp is treated as stale, not new."""
        first = _build_payload(
            event_type=EMAIL_STATUS_DELIVERED,
            message_id=assignment.email_message_id,
            event_timestamp=1000.0,
        )
        process_mailgun_webhook_for_enrollment_code_emails(first)
        assignment.refresh_from_db()
        first_timestamp = assignment.email_status_event_timestamp

        duplicate = _build_payload(
            event_type=EMAIL_STATUS_OPENED,
            message_id=assignment.email_message_id,
            event_timestamp=1000.0,
        )
        result = process_mailgun_webhook_for_enrollment_code_emails(duplicate)

        assert result == assignment
        assignment.refresh_from_db()
        assert assignment.email_status == EMAIL_STATUS_DELIVERED
        assert assignment.email_status_event_timestamp == first_timestamp

    @override_settings(
        MAILGUN_WEBHOOK_VALIDATE_SIGNATURE=True,
        MAILGUN_WEBHOOK_SIGNING_SECRET=SIGNING_SECRET,
    )
    def test_first_event_is_applied_regardless_of_timestamp(self, assignment):
        """There's nothing saved yet, so even an old-looking timestamp should be stored."""
        payload = _build_payload(
            event_type=EMAIL_STATUS_DELIVERED,
            message_id=assignment.email_message_id,
            event_timestamp=1.0,
        )

        result = process_mailgun_webhook_for_enrollment_code_emails(payload)

        assert result == assignment
        assignment.refresh_from_db()
        assert assignment.email_status == EMAIL_STATUS_DELIVERED
        assert assignment.email_status_event_timestamp is not None
