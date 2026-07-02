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

# How many times retry_failed_edx_enrollments will retry a single enrollment
# before giving up on it. Without this, an unrecoverable failure (expired
# course mode, deleted course run, etc) gets re-attempted on every repair run
# forever - see MITXONLINE-5ZV.
OPENEDX_ENROLLMENT_REPAIR_MAX_RETRIES = 5

OPENEDX_USERNAME_MAX_LEN = 30
