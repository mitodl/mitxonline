"""Exceptions for the courses API."""

from rest_framework import status
from rest_framework.exceptions import APIException


class EnrollmentError(APIException):
    """
    Raised when an enrollment request cannot be completed.

    Deliberately excludes any specifics about *why* the enrollment failed
    (e.g. an export compliance decision) - historically we've just told
    learners to contact support in these cases rather than surfacing that
    detail to the client. The underlying cause is logged server-side by the
    code that raises it (e.g. ``courses.api``).
    """

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Unable to complete enrollment. Please contact support."
    default_code = "unable_to_complete_enrollment"


class EnrollmentCreationFailedError(EnrollmentError):
    """Error when the create_run_enrollments fails."""
