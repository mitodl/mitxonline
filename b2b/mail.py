import logging

from django.conf import settings
from mitol.mail.api import get_message_sender
from mitol.mail.messages import TemplatedMessage

from b2b.models import DiscountContractAttachmentRedemption

log = logging.getLogger(__name__)


class EnrollmentCodeAssignmentMessage(TemplatedMessage):
    template_name = "mail/enrollment_code_assignment"
    name = "Enrollment Code Assignment"


def send_enrollment_code_assignment_email(assignment_record_ids):
    """
    Send an enrollment code assignment invite email.

    Args:
        assignment_record_ids list[int]: The IDs for DiscountContractAttachmentRedemption records to send emails for
    """

    # Should make this a utility function and move the map somewhere more general
    from courses.api import ENV_TO_LEARN_HOSTNAME_MAP  # noqa: PLC0415

    learn_hostname = ENV_TO_LEARN_HOSTNAME_MAP.get(
        settings.ENVIRONMENT, "learn.mit.edu"
    )
    assignments = list(
        DiscountContractAttachmentRedemption.objects.filter(
            id__in=assignment_record_ids
        ).select_related("discount", "contract")
    )

    for assignment in assignments:
        code = assignment.discount.discount_code
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
                        "contract_name": assignment.contract.name,
                    },
                )
        except:  # pylint: disable=bare-except  # noqa: E722
            log.exception("Error sending enrollment code assignment email.")
