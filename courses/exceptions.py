"""Exceptions for the courses API."""

from rest_framework import status
from rest_framework.exceptions import APIException


class EnrollmentError(APIException):
    """
    Raised when an enrollment request cannot be completed.

    Deliberately excludes any specifics about *why* the enrollment failed (e.g.
    which export compliance decision came back) rather than surfacing that
    detail to the client. The one thing that varies is an opaque support code
    appended by ``from_cause`` for causes that declare one. The underlying cause
    is logged server-side by the code that raises it (e.g. ``courses.api``).

    Says nothing about contacting support either - clients already pair an
    enrollment failure with their own support copy, so a CTA here doubles up.
    """

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Unable to complete enrollment."
    default_code = "unable_to_complete_enrollment"

    @classmethod
    def from_cause(cls, exc: Exception) -> "EnrollmentError":
        """
        Build an error for `exc`, appending the cause's support code when it
        declares one (see ``compliance.exceptions.ExportComplianceError``).

        A cause without an ``error_code`` yields the unchanged default detail,
        so a new failure mode stays opaque unless it opts in.

        A cause that names the user's own profile fields to fix (see
        ``compliance.exceptions.ExportComplianceDataError.profile_fields``)
        has them added as ``missing_fields``, so the client can ask for them.

        Args:
            exc (Exception): The underlying cause of the enrollment failure

        Returns:
            EnrollmentError: The error to raise from `exc`
        """
        error_code = getattr(exc, "error_code", None)
        if not error_code:
            return cls()
        detail = f"{cls.default_detail} Error code: {error_code}."
        profile_fields = getattr(exc, "profile_fields", None)
        if profile_fields:
            return cls({"detail": detail, "missing_fields": profile_fields})
        return cls(detail)


class EnrollmentCreationFailedError(EnrollmentError):
    """Error when the create_run_enrollments fails."""


class ProgramEntitlementUnavailableError(APIException):
    """
    Raised when a verified program enrollment doesn't entitle the learner to a
    free verified run of a course: they didn't buy the program, or they already
    used its one verified run for that course. The learner has to buy the run,
    so clients should send them to checkout.
    """

    status_code = status.HTTP_402_PAYMENT_REQUIRED
    default_detail = "This course run must be purchased."
    default_code = "program_entitlement_unavailable"
