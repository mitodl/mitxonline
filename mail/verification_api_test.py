"""Tests for verification_api"""

from urllib.parse import quote_plus

import pytest
from django.core.mail import EmailMessage
from django.shortcuts import reverse
from django.test.client import RequestFactory
from mitol.common.pytest_utils import any_instance_of

from mail import verification_api
from users.models import ChangeEmailRequest

pytestmark = [pytest.mark.django_db]


def test_send_verify_email_change_email(mocker, user):
    """Test email change request verification email sends with a link in it"""
    request = RequestFactory().get(reverse("account-settings"))
    change_request = ChangeEmailRequest.objects.create(
        user=user, new_email="abc@example.com"
    )

    send_messages_mock = mocker.patch("mail.api.send_messages")

    verification_api.send_verify_email_change_email(request, change_request)

    send_messages_mock.assert_called_once_with([any_instance_of(EmailMessage)])

    url = "{}?verification_code={}".format(
        request.build_absolute_uri(reverse("account-confirm-email-change")),
        quote_plus(change_request.code),
    )

    email_body = send_messages_mock.call_args[0][0][0].body
    assert url in email_body
