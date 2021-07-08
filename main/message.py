"""Main message classes"""
from mitol.mail.messages import TemplatedMessage


class SupportMessage(TemplatedMessage):
    """Support email message"""

    template_name = "mail/support"
