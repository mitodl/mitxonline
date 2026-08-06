import logging
import uuid

from django.conf import settings
from mitol.common.utils.datetime import now_in_utc
from mitol.mail.api import get_message_sender
from mitol.mail.messages import TemplatedMessage

from b2b.models import ContractPage, DiscountContractAttachmentRedemption

log = logging.getLogger(__name__)

ENROLLMENT_CODE_ASSINGMENT_TAG = "enrollment-code-assignment"


class BaseEnrollmentCodeAssignmentMessage(TemplatedMessage):
    template_name = "mail/enrollment_code_assignment"
    name = "Enrollment Code Assignment"


class EnrollmentCodeAssignmentMessage(BaseEnrollmentCodeAssignmentMessage):
    @staticmethod
    def get_default_headers() -> dict:
        base_headers = TemplatedMessage.get_default_headers()
        headers = base_headers.copy()
        headers["X-Mailgun-Tag"] = ENROLLMENT_CODE_ASSINGMENT_TAG
        return headers


def send_email_helper(  # noqa: PLR0913
    email, code, code_url, organization_name, contract_name, *, is_test=False
):
    message_type = (
        BaseEnrollmentCodeAssignmentMessage
        if is_test
        else EnrollmentCodeAssignmentMessage
    )
    try:
        with get_message_sender(message_type) as sender:
            message = sender.build_message(
                email,
                {
                    "code": code,
                    "code_url": code_url,
                    "organization_name": organization_name,
                    "contract_name": contract_name,
                },
            )
            # send_message swallows exceptions, so we'll favor direct calls to message.send()
            message.send()

            # The message_id is primarily to be used to tie back to mailgun webhook events unambiguously
            # In the case of a local SMTP server the message_id will be none so we just generate a UUID
            if (
                settings.MITOL_MAIL_CONNECTION_BACKEND
                == "anymail.backends.mailgun.EmailBackend"
            ):
                recipient_status = message.anymail_status.recipients.get(email)
                # Message ID is in the following format when pulled from anymail
                # '<20260806133209.67c51081a4f1c478@mitxonline-rc-mail.mitxonline.mit.edu>'
                # The webhook doesn't have the leading or trailing angle brackets, so we'll remove those
                message_id = (
                    recipient_status.message_id.strip("<>")
                    if recipient_status
                    else None
                )
            else:
                message_id = str(uuid.uuid4())

            return message_id
    except:  # pylint: disable=bare-except  # noqa: E722
        log.exception("Error sending enrollment code assignment email.")


def send_enrollment_code_assignment_email(assignment_record_ids):
    """
    Send an enrollment code assignment invite email.

    Args:
        assignment_record_ids list[int]: The IDs for DiscountContractAttachmentRedemption records to send emails for
    """

    assignments = list(
        DiscountContractAttachmentRedemption.objects.filter(
            id__in=assignment_record_ids
        ).select_related("discount", "contract")
    )

    for assignment in assignments:
        code = assignment.discount.discount_code
        code_url = f"{settings.MIT_LEARN_ATTACH_URL}{code}"
        organization_name = assignment.contract.organization.name
        message_id = send_email_helper(
            assignment.assigned_email,
            code,
            code_url,
            organization_name,
            assignment.contract.name,
        )
        if message_id:
            # If we got a message ID from mailgun, we'll treat the message as sent
            # If anything goes wrong after that, it'll come in as a webhook
            # We are going to perform these saves as eagerly as possibly as there's technically
            # a race condition between saving the message ID and webhooks coming in.
            assignment.email_message_id = message_id
            assignment.last_reminder_sent_on = now_in_utc()
            assignment.save(update_fields=["email_message_id", "last_reminder_sent_on"])


def send_test_enrollment_code_assignment_email(email, contract_record_id):
    contract = ContractPage.objects.get(pk=contract_record_id)
    send_email_helper(
        email,
        "PLACEHOLDER_CODE",
        f"{settings.MIT_LEARN_ATTACH_URL}PLACEHOLDER_CODE",
        contract.organization.name,
        contract.name,
        is_test=True,
    )
