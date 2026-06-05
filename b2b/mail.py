"""B2B email sending functions."""

import logging

log = logging.getLogger(__name__)


def send_enrollment_code_assignment_email(redemption):
    """
    Send an enrollment code assignment invite email.

    Args:
        redemption (DiscountContractAttachmentRedemption): The redemption record
            containing the assignee's email, name, and discount code.
    """
    log.info(
        "send_enrollment_code_assignment_email: stub called for redemption %s (email=%s)",
        redemption.pk,
        redemption.assigned_email,
    )
