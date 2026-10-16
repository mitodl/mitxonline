"""Tests for the courses API exceptions."""

from compliance.exceptions import (
    ExportComplianceCheckError,
    ExportComplianceDataError,
    ExportComplianceError,
    ExportComplianceUnavailableError,
)
from courses.exceptions import EnrollmentCreationFailedError, EnrollmentError


def test_from_cause_appends_the_causes_error_code(user):
    """A CyberSource rejection contributes its support code to the detail."""
    exc = ExportComplianceError(user, "REJECT", "102")

    error = EnrollmentError.from_cause(exc)

    assert str(error.detail) == "Unable to complete enrollment. Error code: CS_700."


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


def test_from_cause_uses_the_causes_own_detail_when_it_declares_one(user):
    """An unreachable CyberSource is worth retrying, so the copy says so."""
    exc = ExportComplianceUnavailableError(user, 2)

    error = EnrollmentError.from_cause(exc)

    assert str(error.detail) == (
        "We're unable to complete your enrollment at this time. "
        "Please try again in a few minutes. Error code: CS_503."
    )


def test_from_cause_names_no_mechanism_in_learner_facing_copy(user):
    """
    Whatever a cause contributes, the detail must not disclose that a
    compliance check exists, let alone that it was what failed.
    """
    disclosing = ("compliance", "cybersource", "export", "screening", "sanction")

    for exc in (
        ExportComplianceError(user, "REJECT", "102"),
        ExportComplianceUnavailableError(user, 2),
        ExportComplianceDataError(user, ["bill_to_country"]),
    ):
        detail = str(EnrollmentError.from_cause(exc).detail).lower()

        assert not any(word in detail for word in disclosing), detail


def test_from_cause_preserves_the_subclass(user):
    """`cls` is honored, so a subclass keeps its own identity and detail."""
    error = EnrollmentCreationFailedError.from_cause(
        ExportComplianceError(user, "REJECT", "102")
    )

    assert isinstance(error, EnrollmentCreationFailedError)
    assert str(error.detail).endswith("Error code: CS_700.")
