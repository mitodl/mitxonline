"""Courseware constants"""

PLATFORM_EDX = "edx"
# List of all currently-supported openedx platforms
OPENEDX_PLATFORMS = (PLATFORM_EDX,)
# Currently-supported openedx platforms in a ChoiceField-friendly format
OPENEDX_PLATFORM_CHOICES = zip(OPENEDX_PLATFORMS, OPENEDX_PLATFORMS)
EDX_ENROLLMENT_VERIFIED_MODE = "verified"
EDX_ENROLLMENT_AUDIT_MODE = "audit"
EDX_DEFAULT_ENROLLMENT_MODE = EDX_ENROLLMENT_AUDIT_MODE
EDX_ENROLLMENTS_PAID_MODES = [
    EDX_ENROLLMENT_VERIFIED_MODE,
]
PRO_ENROLL_MODE_ERROR_TEXTS = (
    f"The [{EDX_DEFAULT_ENROLLMENT_MODE}] course mode is expired or otherwise unavailable for course run",
    f"Specified course mode '{EDX_DEFAULT_ENROLLMENT_MODE}' unavailable for course",
)
# The amount of minutes after creation that a openedx model record should be eligible for repair
OPENEDX_REPAIR_GRACE_PERIOD_MINS = 5

OPENEDX_USERNAME_MAX_LEN = 30
