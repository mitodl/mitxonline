"""API for email verifications"""

from urllib.parse import quote_plus

from django.urls import reverse

from mail import api
from mail.constants import EMAIL_CHANGE_EMAIL


def send_verify_email_change_email(request, change_request):
    """
    Sends a verification email for a user email change
    Args:
        request (django.http.Request): the http request we're sending this email for
        change_request (ChangeEmailRequest): the change request to send the confirmation for
    """

    url = "{}?verification_code={}".format(
        request.build_absolute_uri(reverse("account-confirm-email-change")),
        quote_plus(change_request.code),
    )

    api.send_messages(
        list(
            api.messages_for_recipients(
                [
                    (
                        change_request.new_email,
                        api.context_for_user(extra_context={"confirmation_url": url}),
                    )
                ],
                EMAIL_CHANGE_EMAIL,
            )
        )
    )
