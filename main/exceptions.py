"""Exception related classes and functions"""

from rest_framework import exceptions, views

from compliance.exceptions import ExportComplianceCheckError
from courses.exceptions import CountryBlockedError, EnrollmentError


def exception_handler(exc, context):
    """Override DRF exception_handler to slightly change format of error response"""
    if isinstance(exc, CountryBlockedError | ExportComplianceCheckError):
        # Don't propagate the specifics of the compliance decision (or the
        # blocked country) to the client - only an opaque support code and the
        # profile fields to fix, if the cause declares them. The underlying
        # cause is logged where it's raised.
        exc = EnrollmentError.from_cause(exc)
    if isinstance(exc, exceptions.ValidationError) and isinstance(
        exc.detail, list | dict
    ):
        exc = exceptions.ValidationError(
            detail={"errors": exc.detail}, code=exc.status_code
        )
    return views.exception_handler(exc, context)
