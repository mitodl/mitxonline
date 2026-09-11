"""Exceptions for the courses API."""

from rest_framework import status
from rest_framework.exceptions import APIException


class EnrollmentError(APIException):
    """
    Raised when an enrollment request cannot be completed.

    Deliberately excludes any specifics about *why* the enrollment failed (e.g.
    which export compliance decision came back) - historically we've just told
    learners to contact support in these cases rather than surfacing that detail
    to the client. The one thing that varies is an opaque support code appended
    by ``from_cause`` for causes that declare one. The underlying cause is
    logged server-side by the code that raises it (e.g. ``courses.api``).
    """

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Unable to complete enrollment. Please contact support."
    default_code = "unable_to_complete_enrollment"

    @classmethod
    def from_cause(cls, exc: Exception) -> "EnrollmentError":
        """
        Build an error for `exc`, appending the cause's support code when it
        declares one (see ``compliance.exceptions.ExportComplianceError``).

        A cause without an ``error_code`` yields the unchanged default detail,
        so a new failure mode stays opaque unless it opts in.

        Args:
            exc (Exception): The underlying cause of the enrollment failure

        Returns:
            EnrollmentError: The error to raise from `exc`
        """
        error_code = getattr(exc, "error_code", None)
        if not error_code:
            return cls()
        return cls(f"{cls.default_detail} Error code: {error_code}")


class EnrollmentCreationFailedError(EnrollmentError):
    """Error when the create_run_enrollments fails."""
