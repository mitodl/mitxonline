from b2b.models import DiscountContractAttachmentRedemption


def is_redeemed_attachment_record(
    assignment_record: DiscountContractAttachmentRedemption,
) -> bool:
    return assignment_record.user or assignment_record.redeemed_on
