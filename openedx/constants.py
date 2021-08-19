"""Courseware constants"""

PLATFORM_EDX = "edx"
# List of all currently-supported openedx platforms
OPENEDX_PLATFORMS = (PLATFORM_EDX,)
# Currently-supported openedx platforms in a ChoiceField-friendly format
OPENEDX_PLATFORM_CHOICES = zip(OPENEDX_PLATFORMS, OPENEDX_PLATFORMS)
EDX_ENROLLMENT_PRO_MODE = "no-id-professional"
EDX_ENROLLMENT_AUDIT_MODE = "audit"
EDX_DEFAULT_ENROLLMENT_MODE = EDX_ENROLLMENT_AUDIT_MODE
PRO_ENROLL_MODE_ERROR_TEXTS = (
    "The [{}] course mode is expired or otherwise unavailable for course run".format(
        EDX_DEFAULT_ENROLLMENT_MODE
    ),
    "Specified course mode '{}' unavailable for course".format(
        EDX_DEFAULT_ENROLLMENT_MODE
    ),
)
# The amount of minutes after creation that a openedx model record should be eligible for repair
OPENEDX_REPAIR_GRACE_PERIOD_MINS = 5
