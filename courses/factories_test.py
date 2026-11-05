"""Test for factories."""

import pytest

from courses.factories import CourseRunFactory

pytestmark = pytest.mark.django_db


def test_courserun_completed_trait():
    """Test that the completed trait on CourseRunFactory generates dates properly."""

    for run in CourseRunFactory.create_batch(100, completed=True):
        assert run.start_date <= run.end_date
        assert run.enrollment_start <= run.enrollment_end
        assert run.enrollment_end <= run.end_date
        assert run.enrollment_start <= run.start_date
