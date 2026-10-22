"""Exceptions for the courses API."""

from rest_framework import status
from rest_framework.exceptions import APIException


class EnrollmentError(APIException):
    """
    Raised when an enrollment request cannot be completed.

    Deliberately excludes any specifics about *why* the enrollment failed (e.g.
    which export compliance decision came back) rather than surfacing that
    detail to the client. What varies is an opaque support code appended by
    ``from_cause`` for causes that declare one, and - for a cause that declares
    ``enrollment_detail`` - the sentence it replaces ``default_detail`` with.
    Neither may name the mechanism that failed. The underlying cause is logged
    server-side by the code that raises it (e.g. ``courses.api``).

    Says nothing about contacting support either - clients already pair an
    enrollment failure with their own support copy, so a CTA here doubles up.
    """

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Unable to complete enrollment."
    default_code = "unable_to_complete_enrollment"

    @classmethod
    def from_cause(cls, exc: Exception) -> "EnrollmentError":
        """
        Build an error for `exc` from the cause's own ``enrollment_detail``
        when it declares one, appending its support code when it declares one
        (see ``compliance.exceptions``).

        A cause declaring neither yields the unchanged default detail, so a new
        failure mode stays opaque unless it opts in. A cause that *does* opt in
        still only gets to choose between opaque sentences: a retryable failure
        wants "try again" where a terminal one does not, and that difference is
        tellable without naming what went wrong.

        Args:
            exc (Exception): The underlying cause of the enrollment failure

        Returns:
            EnrollmentError: The error to raise from `exc`
        """
        detail = getattr(exc, "enrollment_detail", None) or cls.default_detail
        error_code = getattr(exc, "error_code", None)
        if not error_code:
            return cls(detail)
        return cls(f"{detail} Error code: {error_code}.")


class EnrollmentCreationFailedError(EnrollmentError):
    """Error when the create_run_enrollments fails."""
