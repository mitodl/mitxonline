import logging

from mitol.mail.api import get_message_sender
from mitol.mail.messages import TemplatedMessage

log = logging.getLogger()


class EnrollmentCodeAssignmentMessage(TemplatedMessage):
    template_name = "mail/enrollment_code_assignment"
    name = "Enrollment Code Assignment"


def send_enrollment_code_assignment_email(assignment, code):
    """
    Send an enrollment code assignment invite email.

    Args:
        assignment (DiscountContractAttachmentRedemption): The assignment record
            containing the assignee's email, name, and discount code.
        code (str): The code assigned to the redemption.
    """
    try:
        with get_message_sender(EnrollmentCodeAssignmentMessage) as sender:
            sender.build_and_send_message(
                assignment.assigned_email,
                {
                    "assignment": assignment,
                    "code": code,
                    "code_url": "",
                    "organization_name": "",
                },
            )
    except:  # pylint: disable=bare-except  # noqa: E722
        log.exception("Error sending enrollment code assignment email.")
