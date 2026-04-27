"""Tests for hubspot_sync.task_helpers"""

import pytest

from ecommerce.factories import ProductFactory
from hubspot_sync.task_helpers import (
    sync_hubspot_cart_add,
    sync_hubspot_deal,
    sync_hubspot_product,
    sync_hubspot_user,
)
from users.factories import UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def mock_exception_log(settings, mocker):
    """Return a mocked log.exception object"""
    settings.MITOL_HUBSPOT_API_PRIVATE_TOKEN = "faketoken"  # noqa: S105
    return mocker.patch("hubspot_sync.task_helpers.log.exception")


@pytest.mark.parametrize("raise_exc", [True, False])
def test_sync_hubspot_deal_uai_order_with_uai_token(
    mocker, mock_exception_log, hubspot_order, raise_exc, settings
):
    """sync_hubspot_deal should use UAI token for UAI orders when available"""
    settings.MITOL_HUBSPOT_API_PRIVATE_TOKEN = "regular-token"  # noqa: S105
    settings.UAI_MITOL_HUBSPOT_API_PRIVATE_TOKEN = "uai-token"  # noqa: S105

    mock_sync = mocker.patch(
        "hubspot_sync.task_helpers.tasks.sync_deal_with_hubspot_targeted.apply_async",
        side_effect=(ConnectionError if raise_exc else None),
    )
    mocker.patch("hubspot_sync.task_helpers.is_uai_order", return_value=True)

    sync_hubspot_deal(hubspot_order)
    mock_sync.assert_called_once_with(
        args=(hubspot_order.id,), kwargs={"is_uai": True}, countdown=10
    )

    if raise_exc:
        mock_exception_log.assert_called_once_with(
            "Exception calling sync_deal_with_hubspot_targeted for order %d",
            hubspot_order.id,
        )
    else:
        mock_exception_log.assert_not_called()


@pytest.mark.parametrize("raise_exc", [True, False])
def test_sync_hubspot_deal_non_uai_order(
    mocker, mock_exception_log, hubspot_order, raise_exc, settings
):
    """sync_hubspot_deal should use regular token for non-UAI orders"""
    settings.MITOL_HUBSPOT_API_PRIVATE_TOKEN = "regular-token"  # noqa: S105
    settings.UAI_MITOL_HUBSPOT_API_PRIVATE_TOKEN = "uai-token"  # noqa: S105

    mock_sync = mocker.patch(
        "hubspot_sync.task_helpers.tasks.sync_deal_with_hubspot_targeted.apply_async",
        side_effect=(ConnectionError if raise_exc else None),
    )
    mocker.patch("hubspot_sync.task_helpers.is_uai_order", return_value=False)

    sync_hubspot_deal(hubspot_order)
    mock_sync.assert_called_once_with(
        args=(hubspot_order.id,), kwargs={"is_uai": False}, countdown=10
    )

    if raise_exc:
        mock_exception_log.assert_called_once_with(
            "Exception calling sync_deal_with_hubspot_targeted for order %d",
            hubspot_order.id,
        )
    else:
        mock_exception_log.assert_not_called()


@pytest.mark.parametrize("raise_exc", [True, False])
def test_sync_hubspot_user(mocker, mock_exception_log, user, raise_exc):
    """sync_hubspot_user should call tasks.sync_contact_with_hubspot.delay and log any exception"""
    mock_sync = mocker.patch(
        "hubspot_sync.task_helpers.tasks.sync_contact_with_hubspot.delay",
        side_effect=(ConnectionError if raise_exc else None),
    )
    sync_hubspot_user(user)
    mock_sync.assert_called_once_with(user.id)
    if raise_exc:
        mock_exception_log.assert_called_once_with(
            "Exception calling sync_contact_with_hubspot for user %s", user.edx_username
        )
    else:
        mock_exception_log.assert_not_called()


def test_sync_hubspot_user_skips_b2b_users(mocker, settings):
    """sync_hubspot_user should skip B2B users and not call HubSpot sync"""
    settings.MITOL_HUBSPOT_API_PRIVATE_TOKEN = "faketoken"  # noqa: S105

    mock_sync = mocker.patch(
        "hubspot_sync.task_helpers.tasks.sync_contact_with_hubspot.delay"
    )
    mock_info_log = mocker.patch("hubspot_sync.task_helpers.log.info")

    # Mock the global QuerySet.exists to avoid any calls during user creation
    mock_exists_global = mocker.patch(
        "django.db.models.query.QuerySet.exists",
        return_value=False,  # Initially False for user creation
    )

    # Create a user (this might trigger some syncs during creation)
    user = UserFactory.create()

    # Reset the mocks after user creation to clear any calls that happened during setup
    mock_sync.reset_mock()
    mock_info_log.reset_mock()

    # Now set up the mock to return True for B2B check
    mock_exists_global.return_value = True

    # Call the function we're actually testing
    sync_hubspot_user(user)

    # Should not call the sync task
    mock_sync.assert_not_called()

    # Should log that user was skipped
    mock_info_log.assert_called_once_with(
        "Skipping HubSpot sync for B2B user %s (user_id=%d)",
        user.edx_username,
        user.id,
    )


def test_sync_hubspot_user_syncs_regular_users(mocker, settings):
    """sync_hubspot_user should sync regular users (without B2B contracts)"""
    settings.MITOL_HUBSPOT_API_PRIVATE_TOKEN = "faketoken"  # noqa: S105

    mock_sync = mocker.patch(
        "hubspot_sync.task_helpers.tasks.sync_contact_with_hubspot.delay"
    )
    mock_info_log = mocker.patch("hubspot_sync.task_helpers.log.info")

    # Create a regular user without any B2B contracts
    user = UserFactory.create()

    # Reset mocks after user creation to ignore any calls during setup
    mock_sync.reset_mock()
    mock_info_log.reset_mock()

    # Debug: Check the user has no contracts
    print(f"Regular User ID: {user.id}")
    print(f"regular user.b2b_contracts.exists(): {user.b2b_contracts.exists()}")
    print(f"regular user.b2b_contracts.count(): {user.b2b_contracts.count()}")

    # Call the function we're actually testing
    sync_hubspot_user(user)

    # Should call the sync task
    mock_sync.assert_called_once_with(user.id)

    # Should not log anything about B2B users
    mock_info_log.assert_not_called()

    # Should not log any skip message
    mock_info_log.assert_not_called()


@pytest.mark.parametrize("raise_exc", [True, False])
def test_sync_hubspot_product(mocker, mock_exception_log, raise_exc):
    """sync_hubspot_product should call tasks.sync_product_with_hubspot.delay and log any exception"""
    mock_sync = mocker.patch(
        "hubspot_sync.task_helpers.tasks.sync_product_with_hubspot.delay",
        side_effect=(ConnectionError if raise_exc else None),
    )
    product = ProductFactory.build()
    sync_hubspot_product(product)
    mock_sync.assert_called_once_with(product.id)
    if raise_exc:
        mock_exception_log.assert_called_once_with(
            "Exception calling sync_product_with_hubspot for product %d", product.id
        )
    else:
        mock_exception_log.assert_not_called()


@pytest.mark.parametrize("raise_exc", [True, False])
def test_sync_hubspot_cart_add(mocker, mock_exception_log, user, raise_exc):
    """sync_hubspot_cart_add should call sync_cart_add_event_with_hubspot.apply_async and log any exception"""
    mock_sync = mocker.patch(
        "hubspot_sync.task_helpers.tasks.sync_cart_add_event_with_hubspot.apply_async",
        side_effect=(ConnectionError if raise_exc else None),
    )
    product = ProductFactory.build()
    sync_hubspot_cart_add(user, product, is_uai=True)
    mock_sync.assert_called_once_with(
        args=(user.id, product.id),
        kwargs={"is_uai_course": True},
        countdown=5,
    )
    if raise_exc:
        mock_exception_log.assert_called_once_with(
            "Exception calling sync_cart_add_event_with_hubspot for user %s and product %d",
            user.edx_username,
            product.id,
        )
    else:
        mock_exception_log.assert_not_called()
