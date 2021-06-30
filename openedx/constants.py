"""Courseware constants"""

PLATFORM_EDX = "edx"
# List of all currently-supported openedx platforms
OPENEDX_PLATFORMS = (PLATFORM_EDX,)
# Currently-supported openedx platforms in a ChoiceField-friendly format
OPENEDX_PLATFORM_CHOICES = zip(OPENEDX_PLATFORMS, OPENEDX_PLATFORMS)
EDX_ENROLLMENT_PRO_MODE = "no-id-professional"
EDX_ENROLLMENT_AUDIT_MODE = "audit"
PRO_ENROLL_MODE_ERROR_TEXTS = (
    "The [{}] course mode is expired or otherwise unavailable for course run".format(
        EDX_ENROLLMENT_PRO_MODE
    ),
    "Specified course mode '{}' unavailable for course".format(EDX_ENROLLMENT_PRO_MODE),
)
# The amount of minutes after creation that a openedx model record should be eligible for repair
OPENEDX_REPAIR_GRACE_PERIOD_MINS = 5
