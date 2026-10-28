"""Tests for the DRF exception handler"""

import pytest
from rest_framework import status

from compliance.exceptions import (
    ExportComplianceCheckError,
    ExportComplianceDataError,
    ExportComplianceError,
)
from main.exceptions import exception_handler


@pytest.mark.parametrize(
    ("exc_factory", "expected"),
    [
        (
            lambda user: ExportComplianceError(user, "REJECT", "102"),
            {
                "detail": "Unable to complete enrollment. Error code: CS_700.",
                "reason_code": "CS_700",
            },
        ),
        (
            lambda user: ExportComplianceDataError(user, ["postal_code"]),
            {
                "detail": "Unable to complete enrollment. Error code: CS_701.",
                "reason_code": "CS_701",
                "missing_fields": ["postal_code"],
            },
        ),
        (
            lambda user: ExportComplianceCheckError("something else"),  # noqa: ARG005
            {"detail": "Unable to complete enrollment."},
        ),
    ],
)
def test_exception_handler_converts_compliance_errors(user, exc_factory, expected):
    """Compliance failures from any API view become an opaque 400."""
    response = exception_handler(exc_factory(user), {})

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data == expected


def test_exception_handler_leaves_other_errors_alone():
    """Errors DRF doesn't handle still propagate as 500s."""
    assert exception_handler(ValueError("boom"), {}) is None
