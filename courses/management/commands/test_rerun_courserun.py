"""Tests for the rerun_courserun management command."""

from datetime import UTC, datetime

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from courses.factories import CourseRunFactory

pytestmark = [pytest.mark.django_db]

COMMAND = "rerun_courserun"


@pytest.fixture
def mock_rerun(mocker):
    """Patch rerun_course_run so no run or edX clone is created."""
    return mocker.patch(
        "courses.management.commands.rerun_courserun.rerun_course_run",
        return_value=CourseRunFactory.build(),
    )


@pytest.mark.parametrize(
    ("option", "expected"),
    [
        (None, None),
        ("2027-03-02T23:59:00Z", datetime(2027, 3, 2, 23, 59, tzinfo=UTC)),
    ],
)
def test_upgrade_deadline_passed_through(mock_rerun, option, expected):
    """--upgrade-deadline is passed to rerun_course_run, and is None if not set."""
    base_run = CourseRunFactory.create()
    args = ["--upgrade-deadline", option] if option else []

    call_command(COMMAND, base_run.courseware_id, "--run-tag", "9T2099", *args)

    assert mock_rerun.call_args.kwargs["upgrade_deadline"] == expected


def test_upgrade_deadline_requires_timezone(mock_rerun):
    """A deadline without a timezone is rejected rather than guessed."""
    base_run = CourseRunFactory.create()

    with pytest.raises(CommandError, match="must include a timezone"):
        call_command(
            COMMAND,
            base_run.courseware_id,
            "--run-tag",
            "9T2099",
            "--upgrade-deadline",
            "2027-03-02T23:59:00",
        )

    mock_rerun.assert_not_called()
