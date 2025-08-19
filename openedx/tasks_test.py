"""Courseware tasks"""

import pytest

from openedx import tasks
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
