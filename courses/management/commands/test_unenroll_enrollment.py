"""Tests for Unenroll Enrollment management command"""

import pytest

from django.core.management.base import CommandError

from courses.constants import ENROLL_CHANGE_STATUS_UNENROLLED
from courses.factories import (
    CourseRunFactory,
    CourseRunEnrollmentFactory,
)
from courses.management.commands import unenroll_enrollment
from users.factories import UserFactory

pytestmark = [pytest.mark.django_db]


def test_unenroll_enrollment_no_argument():
    """Test that command throws error when no input is provided"""

    with pytest.raises(CommandError) as command_error:
        unenroll_enrollment.Command().handle()
    assert (
        str(command_error.value)
        == "Could not find a user with <username or email>="
    )


def test_unenroll_enrollment_invalid_run():
    """
    Test that unenroll_enrollment management command throws proper error when
    no valid course run is supplied
    """

    test_user = UserFactory.create()
    with pytest.raises(CommandError) as command_error:
        unenroll_enrollment.Command().handle(user=test_user.username)
    assert str(
        command_error.value
    ) == "Could not find course run with courseware_id={}".format(None)

    with pytest.raises(CommandError) as command_error:
        unenroll_enrollment.Command().handle(user=test_user.username, run="test")
    assert (
        str(command_error.value) == "Could not find course run with courseware_id=test"
    )


def test_unenroll_enrollment_invalid_user():
    """Test that the command throws proper error when user is invalid arguments"""
    run = CourseRunFactory.create()

    with pytest.raises(CommandError) as command_error:
        unenroll_enrollment.Command().handle(
            user="test",
            run=run.courseware_id,
        )
    assert (
        str(command_error.value)
        == "Could not find a user with <username or email>=test"
    )


def test_unenroll_enrollment(mocker):
    """
    Test that user unenrolled from the course properly
    """
    enrollment = CourseRunEnrollmentFactory.create(edx_enrolled=True)
    assert enrollment.change_status is None
    with pytest.raises(CommandError) as command_error:
        unenroll_enrollment.Command().handle(
            run=enrollment.run.courseware_id,
            user=enrollment.user.username,
        )
    edx_unenroll = mocker.patch("courses.api.unenroll_edx_course_run")
    edx_unenroll.assert_called_once_with(enrollment)
    enrollment.refresh_from_db()
    assert enrollment.change_status == ENROLL_CHANGE_STATUS_UNENROLLED


def test_unenroll_enrollment_without_edx(user):
    """
    Test that user unenrolled from the course properly
    """
    run = CourseRunFactory(user=user)
    enrollment = CourseRunEnrollmentFactory(
        user=user,
        runs=run
    )
    assert enrollment.change_status is None
    with pytest.raises(CommandError) as command_error:
        unenroll_enrollment.Command().handle(
            run=enrollment.run.courseware_id,
            user=enrollment.user.username,
            keep_failed_enrollments=True
        )
    assert str(command_error.value) is None
    enrollment.refresh_from_db()
    assert enrollment.change_status == ENROLL_CHANGE_STATUS_UNENROLLED
