"""Tests for compliance app models."""

import pytest
from django.core.exceptions import ValidationError
from mitol.common.utils.datetime import now_in_utc

from compliance.factories import ExportComplianceLogFactory
from compliance.models import ExportComplianceDecision
from courses.factories import CourseRunFactory, ProgramRunFactory
from users.factories import UserFactory

pytestmark = [pytest.mark.django_db]


@pytest.mark.parametrize(
    ("decision", "expected"),
    [
        (ExportComplianceDecision.COMPLETED, True),
        (ExportComplianceDecision.MANUALLY_APPROVED, True),
        (ExportComplianceDecision.INVALID_REQUEST, False),
        (ExportComplianceDecision.DECLINED, False),
        ("", False),
    ],
)
def test_accepted(decision, expected):
    """Accepted should be True only for COMPLETED/MANUALLY_APPROVED decisions."""
    approval_kwargs = (
        {"approved_by": UserFactory.create(), "approved_on": now_in_utc()}
        if decision == ExportComplianceDecision.MANUALLY_APPROVED
        else {}
    )
    log_entry = ExportComplianceLogFactory.create(decision=decision, **approval_kwargs)
    assert log_entry.accepted is expected


def test_manually_approved_requires_approval_fields():
    """Saving a MANUALLY_APPROVED log without approved_by/approved_on should fail."""
    with pytest.raises(ValidationError):
        ExportComplianceLogFactory.create(
            decision=ExportComplianceDecision.MANUALLY_APPROVED,
            approved_by=None,
            approved_on=None,
        )


def test_manually_approved_with_approval_fields_succeeds():
    """Saving a MANUALLY_APPROVED log with approved_by/approved_on set should succeed."""
    approver = UserFactory.create()
    log_entry = ExportComplianceLogFactory.create(
        decision=ExportComplianceDecision.MANUALLY_APPROVED,
        approved_by=approver,
        approved_on=now_in_utc(),
    )
    assert log_entry.approved_by == approver
    assert log_entry.approved_on is not None
    assert log_entry.accepted is True


def test_courseware_object_resolves_course_run():
    """courseware_object should resolve to the CourseRun it was created with."""
    run = CourseRunFactory.create()
    log_entry = ExportComplianceLogFactory.create(courseware_object=run)
    assert log_entry.courseware_object == run


def test_courseware_object_resolves_program_run():
    """courseware_object should resolve to the ProgramRun it was created with."""
    run = ProgramRunFactory.create()
    log_entry = ExportComplianceLogFactory.create(courseware_object=run)
    assert log_entry.courseware_object == run
