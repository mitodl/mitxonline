"""
Utils for mail
"""

import logging
from urllib.parse import urljoin

from django.conf import settings
from django.core.exceptions import ValidationError
from mitol.mail.api import get_message_sender

from flexiblepricing.constants import (
    FLEXIBLE_PRICE_EMAIL_APPROVAL_MESSAGE,
    FLEXIBLE_PRICE_EMAIL_APPROVAL_SUBJECT,
    FLEXIBLE_PRICE_EMAIL_DOCUMENTS_RECEIVED_MESSAGE,
    FLEXIBLE_PRICE_EMAIL_DOCUMENTS_RECEIVED_SUBJECT,
    FLEXIBLE_PRICE_EMAIL_RESET_DASHBOARD_MESSAGE,
    FLEXIBLE_PRICE_EMAIL_RESET_MESSAGE,
    FLEXIBLE_PRICE_EMAIL_RESET_SUBJECT,
    FlexiblePriceStatus,
)
from flexiblepricing.messages import FlexiblePriceStatusChangeMessage

log = logging.getLogger(__name__)

RECIPIENT_VARIABLE_NAMES = {
    "PreferredName": "preferred_name",
    "Email": "email",
}


def get_flexible_price_form_url(flexible_price):
    """
    The absolute URL of the live financial aid form the learner submitted, or None
    if there is no submission or its form page is unpublished or not routable.
    """
    submission = flexible_price.cms_submission
    if not submission or not submission.page.live:
        return None
    url_parts = submission.page.specific.get_url_parts()
    if not url_parts:
        return None
    return urljoin(settings.SITE_BASE_URL, url_parts[2])


def generate_flexible_price_email(flexible_price):
    """
    Sends the learner an email about a FlexiblePrice status update. Accepted statuses are
    FlexiblePriceStatus.APPROVED, FlexiblePriceStatus.PENDING_MANUAL_APPROVAL (documents
    have been received) and FlexiblePriceStatus.RESET.
    Args:
        flexible_price (FlexiblePrice): The FlexiblePrice object in question
    """
    program_name = flexible_price.courseware_object.title
    if flexible_price.status == FlexiblePriceStatus.APPROVED:
        price = flexible_price.tier.discount.friendly_format()
        message = FLEXIBLE_PRICE_EMAIL_APPROVAL_MESSAGE.format(
            program_name=program_name,
            price=price,
            dashboard_url=settings.MIT_LEARN_DASHBOARD_URL,
        )
        subject = FLEXIBLE_PRICE_EMAIL_APPROVAL_SUBJECT.format(
            program_name=program_name
        )
    elif flexible_price.status == FlexiblePriceStatus.PENDING_MANUAL_APPROVAL:
        message = FLEXIBLE_PRICE_EMAIL_DOCUMENTS_RECEIVED_MESSAGE
        subject = FLEXIBLE_PRICE_EMAIL_DOCUMENTS_RECEIVED_SUBJECT.format(
            program_name=program_name
        )
    elif flexible_price.status == FlexiblePriceStatus.RESET:
        form_url = get_flexible_price_form_url(flexible_price)
        message = (
            FLEXIBLE_PRICE_EMAIL_RESET_MESSAGE.format(form_url=form_url)
            if form_url
            else FLEXIBLE_PRICE_EMAIL_RESET_DASHBOARD_MESSAGE.format(
                dashboard_url=settings.MIT_LEARN_DASHBOARD_URL
            )
        )
        subject = FLEXIBLE_PRICE_EMAIL_RESET_SUBJECT.format(program_name=program_name)
    else:
        raise ValidationError(
            "Invalid status on FlexiblePrice for generate_flexible_price_email()"  # noqa: EM101
        )
    try:
        with get_message_sender(FlexiblePriceStatusChangeMessage) as sender:
            sender.build_and_send_message(
                flexible_price.user.email,
                {
                    "subject": subject,
                    "first_name": flexible_price.user.name,
                    "message": message,
                    "program_name": program_name,
                },
            )
    except:  # noqa: E722
        log.exception("Error sending flexible price request status change email")


def send_financial_assistance_request_denied_email(
    financial_assistance_request, email_subject, email_body
):
    log.info(
        f"Sending Financial Assistance request denied email to {financial_assistance_request.user.email}"  # noqa: G004
    )
    try:
        with get_message_sender(FlexiblePriceStatusChangeMessage) as sender:
            sender.build_and_send_message(
                financial_assistance_request.user.email,
                {
                    "subject": email_subject,
                    "first_name": financial_assistance_request.user.name,
                    "message": email_body,
                    "program_name": financial_assistance_request.courseware_object.title,
                },
            )
    except:  # noqa: E722
        log.exception("Error sending flexible price request status change email")
