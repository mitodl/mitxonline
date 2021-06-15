"""mitx_online utilities"""
from enum import Flag, auto

from django.conf import settings
from django.http import HttpRequest
from mitol.common.utils.urls import remove_password_from_url
from mitol.common.utils.webpack import webpack_public_path


class FeatureFlag(Flag):
    """
    FeatureFlag enum

    Members should have values of increasing powers of 2 (1, 2, 4, 8, ...)

    """

    EXAMPLE_FEATURE = auto()


def get_js_settings(request: HttpRequest):
    """
    Get the set of JS settings

    Args:
        request (django.http.HttpRequest) the current request

    Returns:
        dict: the settings object
    """
    return {
        "gaTrackingID": settings.GA_TRACKING_ID,
        "environment": settings.ENVIRONMENT,
        "public_path": webpack_public_path(request),
        "release_version": settings.VERSION,
        "sentry_dsn": remove_password_from_url(settings.SENTRY_DSN),
        "support_email": settings.EMAIL_SUPPORT,
        "site_name": settings.SITE_NAME,
    }
