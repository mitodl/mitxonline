"""Tests for the ProcessMailgunWebhook view."""

import pytest
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from b2b.mail import ENROLLMENT_CODE_ASSINGMENT_TAG
from b2b.models import EMAIL_STATUS_DELIVERED

pytestmark = [pytest.mark.django_db]


def _payload(tags=(ENROLLMENT_CODE_ASSINGMENT_TAG,), event_type=EMAIL_STATUS_DELIVERED):
    return {
        "signature": {
            "token": "some-token",
            "timestamp": "1700000000",
            "signature": "irrelevant-since-validation-is-disabled",
        },
        "event-data": {
            "event": event_type,
            "tags": list(tags),
            "message": {"headers": {"message-id": "message-id-1"}},
        },
    }


@override_settings(MAILGUN_WEBHOOK_VALIDATE_SIGNATURE=False)
def test_webhook_queues_task_for_valid_payload(mocker):
    """A payload that looks like a real, relevant Mailgun event should get queued."""
    mock_task = mocker.patch(
        "b2b.views.v0.manager.queue_process_mailgun_webhook_for_enrollment_code_emails"
    )

    client = APIClient()
    url = reverse("b2b:mailgun-webhook")
    payload = _payload()
    response = client.post(url, data=payload, format="json")

    assert response.status_code == status.HTTP_200_OK
    mock_task.delay.assert_called_once_with(payload)


@override_settings(MAILGUN_WEBHOOK_VALIDATE_SIGNATURE=False)
def test_webhook_does_not_queue_task_for_irrelevant_payload(mocker):
    """Payloads without the relevant tag should be dropped without queueing anything."""
    mock_task = mocker.patch(
        "b2b.views.v0.manager.queue_process_mailgun_webhook_for_enrollment_code_emails"
    )

    client = APIClient()
    url = reverse("b2b:mailgun-webhook")
    payload = _payload(tags=("some-other-tag",))
    response = client.post(url, data=payload, format="json")

    # We return 200 regardless so Mailgun doesn't retry.
    assert response.status_code == status.HTTP_200_OK
    mock_task.delay.assert_not_called()


@override_settings(MAILGUN_WEBHOOK_VALIDATE_SIGNATURE=False)
def test_webhook_does_not_require_authentication(mocker):
    """The endpoint has no permission classes set, so it should work unauthenticated."""
    mocker.patch(
        "b2b.views.v0.manager.queue_process_mailgun_webhook_for_enrollment_code_emails"
    )

    client = APIClient()
    url = reverse("b2b:mailgun-webhook")
    response = client.post(url, data=_payload(), format="json")

    assert response.status_code == status.HTTP_200_OK
