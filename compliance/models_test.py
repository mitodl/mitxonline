"""Tests for compliance app models."""

import pytest

from compliance.factories import ExportComplianceLogFactory
from courses.factories import CourseRunFactory, ProgramRunFactory

pytestmark = [pytest.mark.django_db]


@pytest.mark.parametrize(
    ("decision", "expected"),
    [
        ("ACCEPT", True),
        ("COMPLETED", True),
        ("REJECT", False),
        ("REVIEW", False),
        ("", False),
    ],
)
def test_accepted(decision, expected):
    """Accepted should be True only for ACCEPT/COMPLETED decisions."""
    log_entry = ExportComplianceLogFactory.create(decision=decision)
    assert log_entry.accepted is expected


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
