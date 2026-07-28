"""
context processors for MITxOnline
"""

from django.conf import settings

# pylint: disable=unused-argument


def api_keys(request):  # noqa: ARG001
    """
    Pass a `APIKEYS` dictionary into the template context, which holds
    IDs and secret keys for the various APIs used in this project.
    """
    return {
        "APIKEYS": {
            "GA_TRACKING_ID": settings.GA_TRACKING_ID,
            "GTM_TRACKING_ID": settings.GTM_TRACKING_ID,
        }
    }


def configuration_context(request):  # noqa: ARG001
    """
    Configuration context for django templates.
    """
    return {
        "site_name": settings.SITE_NAME,
        "mit_learn_terms_url": settings.MIT_LEARN_TERMS_URL,
        "mit_learn_privacy_url": settings.MIT_LEARN_PRIVACY_URL,
        "mit_learn_honor_code_url": settings.MIT_LEARN_HONOR_CODE_URL,
    }
