"""Tests for hubspot_sync.task_helpers"""
import pytest

from ecommerce.factories import ProductFactory
from hubspot_sync.task_helpers import (
    sync_hubspot_deal,
    sync_hubspot_product,
    sync_hubspot_user,
)

pytestmark = pytest.mark.django_db


@pytest.fixture()
def mock_exception_log(settings, mocker):
    """Return a mocked log.exception object"""
    settings.MITOL_HUBSPOT_API_PRIVATE_TOKEN = "faketoken"
    return mocker.patch("hubspot_sync.task_helpers.log.exception")


@pytest.mark.parametrize("raise_exc", [True, False])
def test_sync_hubspot_deal(mocker, mock_exception_log, hubspot_order, raise_exc):
    """sync_hubspot_deal should call tasks.sync_contact_with_hubspot.applY_async and log any exception"""
    mock_sync = mocker.patch(
        "hubspot_sync.task_helpers.tasks.sync_deal_with_hubspot.apply_async",
        side_effect=(ConnectionError if raise_exc else None),
    )
    sync_hubspot_deal(hubspot_order)
    mock_sync.assert_called_once_with(args=(hubspot_order), countdown=10)
    if raise_exc:
        mock_exception_log.assert_called_once_with(
            "Exception calling sync_deal_with_hubspot for order %d", hubspot_order.id
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
    mock_sync.assert_called_once_with(user)
    if raise_exc:
        mock_exception_log.assert_called_once_with(
            "Exception calling sync_contact_with_hubspot for user %s", user.username
        )
    else:
        mock_exception_log.assert_not_called()


@pytest.mark.parametrize("raise_exc", [True, False])
def test_sync_hubspot_product(mocker, mock_exception_log, raise_exc):
    """sync_hubspot_product should call tasks.sync_product_with_hubspot.delay and log any exception"""
    mock_sync = mocker.patch(
        "hubspot_sync.task_helpers.tasks.sync_product_with_hubspot.delay",
        side_effect=(ConnectionError if raise_exc else None),
    )
    product = ProductFactory.build()
    sync_hubspot_product(product)
    mock_sync.assert_called_once_with(product)
    if raise_exc:
        mock_exception_log.assert_called_once_with(
            "Exception calling sync_product_with_hubspot for product %d", product.id
        )
    else:
        mock_exception_log.assert_not_called()
