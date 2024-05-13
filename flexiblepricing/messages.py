"""flexible price status change email messages"""

from mitol.mail.messages import TemplatedMessage


class FlexiblePriceStatusChangeMessage(TemplatedMessage):
    template_name = "mail/flexible_price"
    name = "Flexible Price Status Change"
