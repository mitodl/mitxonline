"""Fixtures for B2B tests."""

import pytest
from opaque_keys.edx.keys import CourseKey

from courses.factories import CourseFactory, CourseRunFactory


@pytest.fixture
def contract_ready_course():
    """
    Creates a contract-ready course - i.e. a course with a SOURCE run

    Returns: tuple, course and course run
    """

    course = CourseFactory.create()
    source_course_key = CourseKey.from_string(f"{course.readable_id}+SOURCE")
    source_course_run_key = (
        f"course-v1:{source_course_key.org}+{source_course_key.course}+SOURCE"
    )
    source_course_run = CourseRunFactory.create(
        course=course, courseware_id=source_course_run_key, run_tag="SOURCE"
    )

    return (course, source_course_run)


@pytest.fixture
def mock_course_run_clone(mocker):
    """Mock out the call to clone course runs."""

    return mocker.patch("openedx.tasks.clone_courserun.delay")
