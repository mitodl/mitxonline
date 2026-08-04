"""Courseware constants"""

from enum import StrEnum

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


class UpgradeDeadlineSyncResult(StrEnum):
    """
    Outcome of pushing a CourseRun.upgrade_deadline into the edX verified mode's
    expiration_datetime.
    """

    # The deadline was pushed to edX.
    UPDATED = "updated"
    # edX already had this exact deadline, so no request was made.
    UNCHANGED = "unchanged"
    # The run has no verified mode in edX, so there is nothing to set a deadline on.
    NO_VERIFIED_MODE = "no_verified_mode"
    # The deadline was cleared on our side, but edX's course modes API cannot
    # represent "no deadline" on an update - see CANNOT_CLEAR_DEADLINE_MSG.
    CLEAR_UNSUPPORTED = "clear_unsupported"
    # The FEATURE_SYNC_UPGRADE_DEADLINE_TO_EDX flag is off.
    DISABLED = "disabled"


# The course modes serializer in edX declares expiration_datetime as a
# non-nullable datetime field, so PATCHing an explicit null is rejected.
# edx-api-client sidesteps that by dropping None values from the payload
# entirely, which means a cleared deadline is silently ignored rather than
# erroring. Neither path can clear the deadline, so we detect the case and tell
# the operator to do it by hand.
CANNOT_CLEAR_DEADLINE_MSG = (
    "The upgrade deadline for {courseware_id} was cleared in MITx Online, but "
    "edX's course modes API cannot unset an existing expiration date. edX still "
    "has {edx_deadline}. Clear it manually in the edX Django admin under Course "
    "Modes if the run should have no deadline in edX."
)
