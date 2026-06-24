import logging

from django.conf import settings
from mitol.mail.api import get_message_sender
from mitol.mail.messages import TemplatedMessage

from b2b.models import ContractPage, DiscountContractAttachmentRedemption

log = logging.getLogger(__name__)


class EnrollmentCodeAssignmentMessage(TemplatedMessage):
    template_name = "mail/enrollment_code_assignment"
    name = "Enrollment Code Assignment"


def get_learn_hostname():
    from courses.api import ENV_TO_LEARN_HOSTNAME_MAP  # noqa: PLC0415

    return ENV_TO_LEARN_HOSTNAME_MAP.get(settings.ENVIRONMENT, "learn.mit.edu")


def send_email_helper(email, code, code_url, organization_name, contract_name):
    try:
        with get_message_sender(EnrollmentCodeAssignmentMessage) as sender:
            sender.build_and_send_message(
                email,
                {
                    "code": code,
                    "code_url": code_url,
                    "organization_name": organization_name,
                    "contract_name": contract_name,
                },
            )
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

    learn_hostname = get_learn_hostname()
    for assignment in assignments:
        code = assignment.discount.discount_code
        code_url = f"https://{learn_hostname}/enrollmentcode/{code}"
        organization_name = assignment.contract.organization.name
        send_email_helper(
            assignment.assigned_email,
            code,
            code_url,
            organization_name,
            assignment.contract.name,
        )


def send_test_enrollment_code_assignment_email(email, contract_record_id):
    contract = ContractPage.objects.get(pk=contract_record_id)
    send_email_helper(
        email,
        "PLACEHOLDER_CODE",
        "PLACEHOLDER_URL",
        contract.organization.name,
        contract.name,
    )
