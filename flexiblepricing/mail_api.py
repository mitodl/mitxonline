"""
Utils for mail
"""
import logging

from django.core.exceptions import ValidationError
from mitol.mail.api import get_message_sender

from courses.models import Course
from flexiblepricing.constants import (
    FLEXIBLE_PRICE_EMAIL_APPROVAL_MESSAGE,
    FLEXIBLE_PRICE_EMAIL_APPROVAL_SUBJECT,
    FLEXIBLE_PRICE_EMAIL_DOCUMENTS_RECEIVED_MESSAGE,
    FLEXIBLE_PRICE_EMAIL_DOCUMENTS_RECEIVED_SUBJECT,
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


def generate_flexible_price_email(flexible_price):
    """
    Generates the email subject and body for a FlexiblePrice status update. Accepted statuses are
    FlexiblePriceStatus.APPROVED and FlexiblePriceStatus.PENDING_MANUAL_APPROVAL (documents have been received).
    Args:
        flexible_price (FlexiblePrice): The FlexiblePrice object in question
    Returns:
        dict: {"subject": (str), "body": (str)}
    """
    courseware_course_number_formatted = flexible_price.courseware_object.course_number
    program_name_with_course_number = (
        courseware_course_number_formatted
        + " "
        + flexible_price.courseware_object.title
    )
    if flexible_price.status == FlexiblePriceStatus.APPROVED:
        price = flexible_price.tier.discount.friendly_format()
        message = FLEXIBLE_PRICE_EMAIL_APPROVAL_MESSAGE.format(
            program_name=program_name_with_course_number, price=price
        )
        subject = FLEXIBLE_PRICE_EMAIL_APPROVAL_SUBJECT.format(
            program_name=program_name_with_course_number
        )
    elif flexible_price.status == FlexiblePriceStatus.PENDING_MANUAL_APPROVAL:
        message = FLEXIBLE_PRICE_EMAIL_DOCUMENTS_RECEIVED_MESSAGE
        subject = FLEXIBLE_PRICE_EMAIL_DOCUMENTS_RECEIVED_SUBJECT.format(
            program_name=program_name_with_course_number
        )
    elif flexible_price.status == FlexiblePriceStatus.RESET:
        message = FLEXIBLE_PRICE_EMAIL_RESET_MESSAGE.format(
            program_name=program_name_with_course_number
        )
        subject = FLEXIBLE_PRICE_EMAIL_RESET_SUBJECT.format(
            program_name=program_name_with_course_number
        )
    else:
        raise ValidationError(
            "Invalid status on FlexiblePrice for generate_flexible_price_email()"
        )
    try:
        with get_message_sender(FlexiblePriceStatusChangeMessage) as sender:
            sender.build_and_send_message(
                flexible_price.user.email,
                {
                    "subject": subject,
                    "first_name": flexible_price.user.legal_address.first_name,
                    "message": message,
                    "program_name": program_name_with_course_number,
                },
            )
    except:
        log.exception("Error sending flexible price request status change email")


def send_financial_assistance_request_denied_email(
    financial_assistance_request, email_subject, email_body
):
    log.info(
        f"Sending Financial Assistance request denied email to {financial_assistance_request.user.email}"
    )
    try:
        with get_message_sender(FlexiblePriceStatusChangeMessage) as sender:
            sender.build_and_send_message(
                financial_assistance_request.user.email,
                {
                    "subject": email_subject,
                    "first_name": financial_assistance_request.user.legal_address.first_name,
                    "message": email_body,
                    "program_name": financial_assistance_request.courseware_object.title,
                },
            )
    except:
        log.exception("Error sending flexible price request status change email")
