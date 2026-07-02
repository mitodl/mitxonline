import pytest
from django.core.management import call_command

from courses.factories import CourseRunEnrollmentFactory

pytestmark = [pytest.mark.django_db]


def test_reset_edx_enrollment_retries():
    """Resets the retry count for enrollments matching the given course run"""
    matching = CourseRunEnrollmentFactory.create(
        edx_enrolled=False, edx_enrollment_retry_count=5
    )
    other_run = CourseRunEnrollmentFactory.create(
        edx_enrolled=False, edx_enrollment_retry_count=5
    )
    already_enrolled = CourseRunEnrollmentFactory.create(
        edx_enrolled=True,
        edx_enrollment_retry_count=5,
        run=matching.run,
    )

    call_command("reset_edx_enrollment_retries", "--run", matching.run.courseware_id)

    matching.refresh_from_db()
    other_run.refresh_from_db()
    already_enrolled.refresh_from_db()

    assert matching.edx_enrollment_retry_count == 0
    assert other_run.edx_enrollment_retry_count == 5
    # edx_enrolled=True enrollments aren't touched - there's nothing to repair
    assert already_enrolled.edx_enrollment_retry_count == 5


def test_reset_edx_enrollment_retries_only_exhausted():
    """--only-exhausted limits the reset to enrollments that hit the cap"""
    exhausted = CourseRunEnrollmentFactory.create(
        edx_enrolled=False, edx_enrollment_retry_count=5
    )
    not_exhausted = CourseRunEnrollmentFactory.create(
        edx_enrolled=False, edx_enrollment_retry_count=2, run=exhausted.run
    )

    call_command(
        "reset_edx_enrollment_retries",
        "--run",
        exhausted.run.courseware_id,
        "--only-exhausted",
    )

    exhausted.refresh_from_db()
    not_exhausted.refresh_from_db()

    assert exhausted.edx_enrollment_retry_count == 0
    assert not_exhausted.edx_enrollment_retry_count == 2


def test_reset_edx_enrollment_retries_no_matches(capsys):
    """No matching enrollments should be reported as an error, not silently succeed"""
    call_command("reset_edx_enrollment_retries", "--run", "course-v1:nonexistent+id")

    captured = capsys.readouterr()
    assert "No course run enrollments found" in captured.err
