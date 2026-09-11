"""Tests for the courses API exceptions."""

from compliance.exceptions import (
    ExportComplianceCheckError,
    ExportComplianceDataError,
    ExportComplianceError,
)
from courses.exceptions import EnrollmentCreationFailedError, EnrollmentError


def test_from_cause_appends_the_causes_error_code(user):
    """A CyberSource rejection contributes its support code to the detail."""
    exc = ExportComplianceError(user, "REJECT", "102")

    error = EnrollmentError.from_cause(exc)

    assert str(error.detail) == (
        "Unable to complete enrollment. Please contact support. Error code: CS_700"
    )


def test_from_cause_without_an_error_code_keeps_the_default_detail(user):
    """
    Causes that declare no code stay opaque - notably the missing-profile-data
    case, which never reached CyberSource and so has no CyberSource code.
    """
    for exc in (
        ExportComplianceDataError(user, ["bill_to_country"]),
        ExportComplianceCheckError("something else"),
        ValueError("not a compliance failure at all"),
    ):
        error = EnrollmentError.from_cause(exc)

        assert str(error.detail) == EnrollmentError.default_detail


def test_from_cause_preserves_the_subclass(user):
    """`cls` is honored, so a subclass keeps its own identity and detail."""
    error = EnrollmentCreationFailedError.from_cause(
        ExportComplianceError(user, "REJECT", "102")
    )

    assert isinstance(error, EnrollmentCreationFailedError)
    assert str(error.detail).endswith("Error code: CS_700")
