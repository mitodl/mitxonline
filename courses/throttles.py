"""Throttles for the courses app"""

from django.core.cache import caches
from rest_framework.throttling import UserRateThrottle


class EnrollmentEligibilityThrottle(UserRateThrottle):
    """
    Per-user throttle for the enrollment eligibility endpoints.

    A miss on the cached export compliance result costs a live (billable)
    CyberSource call, so these endpoints are metered. The rate is deliberately
    low: they answer "may I enroll in this one thing" at the point of intent,
    not a bulk pre-flight across a catalogue page.

    Both endpoints share a scope, so the budget is per user rather than per
    endpoint.

    Uses the ``redis`` cache rather than DRF's default. ``CACHES["default"]``
    is a LocMemCache, which is per-process - a throttle backed by it would
    count each gunicorn worker separately and bound nothing in practice.
    """

    scope = "enrollment_eligibility"
    cache = caches["redis"]
