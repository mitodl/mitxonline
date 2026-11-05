"""Tests for users signals"""

import pytest

from users.factories import LegalAddressFactory, UserFactory


@pytest.mark.django_db(transaction=True)
def test_user_creation_triggers_hubspot_sync(mocker):
    """
    Test that creating a user triggers the Hubspot sync.

    UserFactory also creates a LegalAddress via RelatedFactory, so sync_hubspot_user
    is called twice: once from the User post_save signal and once from the LegalAddress
    post_save signal. Both calls carry the same user instance.
    """
    mock_sync = mocker.patch("users.signals.sync_hubspot_user")

    user = UserFactory.create(
        name="Test User",
        email="test@example.com",
    )

    mock_sync.assert_called_with(user)


@pytest.mark.django_db
def test_user_update_does_not_trigger_hubspot_sync(mocker, user):
    """
    Test that updating a user does NOT trigger the Hubspot sync signal.
    """
    mock_sync = mocker.patch("users.signals.sync_hubspot_user")

    user.name = "Updated Name"
    user.save()
    mock_sync.assert_not_called()


@pytest.mark.django_db(transaction=True)
def test_legal_address_create_triggers_hubspot_sync(mocker, user):
    """
    Test that creating a LegalAddress triggers a HubSpot sync for the associated user.

    This covers the case where LegalAddress is created after the initial user sync,
    which would have sent an empty first/last name to HubSpot.
    """
    user.legal_address.delete()
    mock_sync = mocker.patch("users.signals.sync_hubspot_user")

    LegalAddressFactory.create(user=user, first_name="Jane", last_name="Doe")

    mock_sync.assert_called_once_with(user)


@pytest.mark.django_db(transaction=True)
def test_legal_address_update_triggers_hubspot_sync(mocker, user):
    """
    Test that updating a LegalAddress re-syncs the associated user to HubSpot.
    """
    mock_sync = mocker.patch("users.signals.sync_hubspot_user")

    user.legal_address.first_name = "Updated"
    user.legal_address.save()

    mock_sync.assert_called_once_with(user)
