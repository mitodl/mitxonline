"""flexible price status change email messages"""

from mail.messages import SiteTemplatedMessage


class FlexiblePriceStatusChangeMessage(SiteTemplatedMessage):
    template_name = "mail/flexible_price"
    name = "Flexible Price Status Change"
