"""MITxOnline feature flags"""
import posthog
from functools import wraps

from django.conf import settings

IGNORE_EDX_FAILURES = "IGNORE_EDX_FAILURES"
SYNC_ON_DASHBOARD_LOAD = "SYNC_ON_DASHBOARD_LOAD"
ENABLE_NEW_DESIGN = "mitxonline-new-product-page"
ENABLE_NEW_HOME_PAGE_FEATURED = "mitxonline-new-featured-carousel"
ENABLE_NEW_HOME_PAGE_HERO = "mitxonline-new-featured-hero"
ENABLE_NEW_HOME_PAGE_VIDEO = "mitxonline-new-home-page-video-component"


def is_enabled(name, default=None, unique_id=settings.HOSTNAME):
    """
    Returns True if the feature flag is enabled

    Args:
        name (str): feature flag name
        default (bool): default value if not set in settings
        unique_id (str): person identifier passed back to posthog which is the display value for person. I recommend
                         this be a readable id for logged-in users to allow for user flags as well as troubleshooting.
                         For anonymous users, a persistent ID will help with troubleshooting and tracking efforts.

    Returns:
        bool: True if the feature flag is enabled
    """

    return (
        posthog
        and posthog.feature_enabled(
            name,
            unique_id,
            settings.HOSTNAME,
            person_properties={"environment": settings.ENVIRONMENT},
        )
    ) or settings.FEATURES.get(name, default or settings.FEATURES_DEFAULT)


def if_feature_enabled(name, default=None):
    """
    Wrapper that results in a no-op if the given feature isn't enabled, and otherwise
    runs the wrapped function as normal.

    Args:
        name (str): Feature flag name
        default (bool): default value if not set in settings
    """

    def if_feature_enabled_inner(func):  # pylint: disable=missing-docstring
        @wraps(func)
        def wrapped_func(*args, **kwargs):  # pylint: disable=missing-docstring
            if not is_enabled(name, default):
                # If the given feature name is not enabled, do nothing (no-op).
                return
            else:
                # If the given feature name is enabled, call the function and return as normal.
                return func(*args, **kwargs)

        return wrapped_func

    return if_feature_enabled_inner
