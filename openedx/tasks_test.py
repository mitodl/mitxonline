"""Courseware tasks"""

import pytest
from requests.exceptions import HTTPError

from courses.factories import CourseRunFactory
from openedx import tasks
from openedx.exceptions import OpenEdXOAuth2Error
from users.factories import UserFactory

pytestmark = pytest.mark.django_db


def test_create_edx_user_from_id(mocker):
    """Test that create_edx_user_from_id loads a user and calls the API method to create an edX user"""
    patch_create_user = mocker.patch("openedx.tasks.api.create_user")
    user = UserFactory.create()
    tasks.create_edx_user_from_id.delay(user.id)
    patch_create_user.assert_called_once_with(user)


def test_update_edx_user_email_async(mocker):
    """Test that create_edx_user_from_id loads a user and calls the API method to create an edX user"""
    patch_update_user = mocker.patch("openedx.tasks.api.update_edx_user_email")
    user = UserFactory.create()
    tasks.change_edx_user_email_async.delay(user.id)
    patch_update_user.assert_called_once_with(user)


def test_update_edx_user_name_async(mocker):
    """Test that change_edx_user_name_async loads a user and calls the API method to update an edX user name"""
    patch_update_user = mocker.patch("openedx.tasks.api.update_edx_user_name")
    user = UserFactory.create()
    tasks.change_edx_user_name_async.delay(user.id)
    patch_update_user.assert_called_once_with(user)


@pytest.mark.parametrize("disabled", [True, False])
def test_repair_faulty_openedx_users(mocker, settings, disabled):
    """Test that repair_faulty_openedx_users only runs if enabled"""
    patch_repair_users = mocker.patch("openedx.tasks.api.repair_faulty_openedx_users")

    settings.DISABLE_USER_REPAIR_TASK = disabled

    tasks.repair_faulty_openedx_users.delay()

    assert patch_repair_users.call_count == (0 if disabled else 1)


def test_get_clone_courserun_retry_countdown(mocker, settings):
    """Retry countdown should scale by attempt and include jitter."""
    mocker.patch("openedx.tasks.random.randint", return_value=17)
    settings.OPENEDX_COURSE_CLONE_RETRY_DELAY = 300
    settings.OPENEDX_COURSE_CLONE_RETRY_JITTER = 60

    assert tasks._get_clone_courserun_retry_countdown(0) == 317
    assert tasks._get_clone_courserun_retry_countdown(2) == 917


@pytest.mark.parametrize(
    "exc",
    [
        HTTPError("500 Server Error"),
        OpenEdXOAuth2Error("temporary auth failure"),
    ],
)
def test_clone_courserun_retries_transient_errors(mocker, settings, exc):
    """Transient clone failures should be retried with a countdown."""
    run = CourseRunFactory.create()
    settings.OPENEDX_COURSE_CLONE_RETRY_DELAY = 300
    settings.OPENEDX_COURSE_CLONE_RETRY_JITTER = 60
    mocker.patch("openedx.tasks.random.randint", return_value=11)
    mocker.patch("openedx.tasks.api.process_course_run_clone", side_effect=exc)
    mock_retry = mocker.patch.object(
        tasks.clone_courserun,
        "retry",
        side_effect=RuntimeError("retry called"),
    )

    with pytest.raises(RuntimeError, match="retry called"):
        tasks.clone_courserun.run(run.id, "course-v1:MITx+BASE+1T2099")

    mock_retry.assert_called_once_with(exc=exc, countdown=311)


def test_clone_courserun_does_not_retry_non_transient_errors(mocker):
    """Permanent clone failures should bubble up without retrying."""
    run = CourseRunFactory.create()
    error = ValueError("Course already exists in edX")
    mocker.patch("openedx.tasks.api.process_course_run_clone", side_effect=error)
    mock_retry = mocker.patch.object(tasks.clone_courserun, "retry")

    with pytest.raises(ValueError, match="Course already exists in edX"):
        tasks.clone_courserun.run(run.id, "course-v1:MITx+BASE+1T2099")

    mock_retry.assert_not_called()


def test_clone_courserun_logs_exception_after_retry_exhaustion(mocker, settings):
    """Final transient clone failure should be escalated once retries are exhausted."""
    run = CourseRunFactory.create()
    error = HTTPError("500 Server Error")
    settings.OPENEDX_COURSE_CLONE_MAX_RETRIES = 1
    mocker.patch("openedx.tasks.api.process_course_run_clone", side_effect=error)
    mock_retry = mocker.patch.object(tasks.clone_courserun, "retry")
    mock_log_exception = mocker.patch("openedx.tasks.log.exception")

    tasks.clone_courserun.request.retries = 1
    tasks.clone_courserun.max_retries = 1

    with pytest.raises(HTTPError, match="500 Server Error"):
        tasks.clone_courserun.run(run.id, "course-v1:MITx+BASE+1T2099")

    mock_retry.assert_not_called()
    mock_log_exception.assert_called_once()
