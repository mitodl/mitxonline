import logging

from django.conf import settings
from mitol.mail.api import get_message_sender
from mitol.mail.messages import TemplatedMessage

from courses.api import ENV_TO_LEARN_HOSTNAME_MAP

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
    learn_hostname = ENV_TO_LEARN_HOSTNAME_MAP.get(
        settings.ENVIRONMENT, "learn.mit.edu"
    )
    code_url = f"https://{learn_hostname}/enrollmentcode/{code}"
    organization_name = assignment.contract.organization.name

    try:
        with get_message_sender(EnrollmentCodeAssignmentMessage) as sender:
            sender.build_and_send_message(
                assignment.assigned_email,
                {
                    "assignment": assignment,
                    "code": code,
                    "code_url": code_url,
                    "organization_name": organization_name,
                },
            )
    except:  # pylint: disable=bare-except  # noqa: E722
        log.exception("Error sending enrollment code assignment email.")
