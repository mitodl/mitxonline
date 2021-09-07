"""
context processors for MITxOnline
"""
from django.conf import settings

# pylint: disable=unused-argument


def api_keys(request):
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
