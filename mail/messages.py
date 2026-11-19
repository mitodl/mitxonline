"""Shared base classes for mitol-mail TemplatedMessage subclasses"""

from django.conf import settings
from mitol.mail.messages import TemplatedMessage

from mail.constants import EMAIL_SITE_NAME


class SiteTemplatedMessage(TemplatedMessage):
    """
    Base class for app email messages built on mitol-mail's TemplatedMessage.

    Overrides the "site_name" template context so these emails always say
    "MIT Learn", regardless of settings.SITE_NAME (which also drives
    non-email UI and can be overridden per-environment), and gives them
    the MIT Learn dashboard URL to link to.
    """

    @staticmethod
    def get_base_template_context() -> dict:
        return {
            **TemplatedMessage.get_base_template_context(),
            "site_name": EMAIL_SITE_NAME,
            "dashboard_url": settings.MIT_LEARN_DASHBOARD_URL,
        }
