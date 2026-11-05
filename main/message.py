"""Main message classes"""

from mail.messages import SiteTemplatedMessage


class SupportMessage(SiteTemplatedMessage):
    """Support email message"""

    template_name = "mail/support"
