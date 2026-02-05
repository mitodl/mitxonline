"""Tests for users signals"""

import pytest

from users.factories import UserFactory


@pytest.mark.django_db
def test_user_creation_triggers_hubspot_sync(mocker):
    """
    Test that creating a user triggers the Hubspot sync.

    This ensures users created via SCIM are synced to Hubspot.
    """
    mock_sync = mocker.patch("users.signals.sync_hubspot_user")

    user = UserFactory.create(
        name="Test User",
        email="test@example.com",
    )

    mock_sync.assert_called_once_with(user)


@pytest.mark.django_db
def test_user_update_does_not_trigger_hubspot_sync(mocker, user):
    """
    Test that updating a user does NOT trigger the Hubspot sync signal.
    """
    mock_sync = mocker.patch("users.signals.sync_hubspot_user")

    user.name = "Updated Name"
    user.save()
    mock_sync.assert_not_called()
