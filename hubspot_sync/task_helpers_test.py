"""Tests for hubspot_sync.task_helpers"""

import pytest

from ecommerce.factories import ProductFactory
from hubspot_sync.task_helpers import (
    sync_hubspot_cart_add,
    sync_hubspot_deal,
    sync_hubspot_product,
    sync_hubspot_user,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def mock_exception_log(settings, mocker):
    """Return a mocked log.exception object"""
    settings.MITOL_HUBSPOT_API_PRIVATE_TOKEN = "faketoken"  # noqa: S105
    return mocker.patch("hubspot_sync.task_helpers.log.exception")


def test_sync_hubspot_deal_no_lines(mocker, settings):
    """sync_hubspot_deal should not call the task when order has no lines"""
    settings.MITOL_HUBSPOT_API_PRIVATE_TOKEN = "token"  # noqa: S105
    mock_sync = mocker.patch(
        "hubspot_sync.task_helpers.tasks.sync_deal_with_hubspot_targeted.apply_async"
    )
    # Create an order without lines
    order = mocker.Mock()
    order.lines.first.return_value = None
    
    sync_hubspot_deal(order)
    mock_sync.assert_not_called()


def test_sync_hubspot_deal_no_token(mocker, settings, hubspot_order):
    """sync_hubspot_deal should not call the task when no token is available"""
    # Ensure no tokens are set
    settings.MITOL_HUBSPOT_API_PRIVATE_TOKEN = None
    settings.UAI_MITOL_HUBSPOT_API_PRIVATE_TOKEN = None
    
    mock_sync = mocker.patch(
        "hubspot_sync.task_helpers.tasks.sync_deal_with_hubspot_targeted.apply_async"
    )
    
    sync_hubspot_deal(hubspot_order)
    mock_sync.assert_not_called()


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
    mock_sync.assert_called_once_with(args=(hubspot_order.id, "uai-token"), countdown=10)
    
    if raise_exc:
        mock_exception_log.assert_called_once_with(
            "Exception calling sync_deal_with_hubspot_targeted for order %d", hubspot_order.id
        )
    else:
        mock_exception_log.assert_not_called()


@pytest.mark.parametrize("raise_exc", [True, False])
def test_sync_hubspot_deal_uai_order_with_fallback_token(
    mocker, mock_exception_log, hubspot_order, raise_exc, settings
):
    """sync_hubspot_deal should fallback to regular token for UAI orders when UAI token not available"""
    settings.MITOL_HUBSPOT_API_PRIVATE_TOKEN = "regular-token"  # noqa: S105
    # UAI token not set
    if hasattr(settings, 'UAI_MITOL_HUBSPOT_API_PRIVATE_TOKEN'):
        delattr(settings, 'UAI_MITOL_HUBSPOT_API_PRIVATE_TOKEN')
    
    mock_sync = mocker.patch(
        "hubspot_sync.task_helpers.tasks.sync_deal_with_hubspot_targeted.apply_async",
        side_effect=(ConnectionError if raise_exc else None),
    )
    mocker.patch("hubspot_sync.task_helpers.is_uai_order", return_value=True)
    
    sync_hubspot_deal(hubspot_order)
    mock_sync.assert_called_once_with(args=(hubspot_order.id, "regular-token"), countdown=10)
    
    if raise_exc:
        mock_exception_log.assert_called_once_with(
            "Exception calling sync_deal_with_hubspot_targeted for order %d", hubspot_order.id
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
    mock_sync.assert_called_once_with(args=(hubspot_order.id, "regular-token"), countdown=10)
    
    if raise_exc:
        mock_exception_log.assert_called_once_with(
            "Exception calling sync_deal_with_hubspot_targeted for order %d", hubspot_order.id
        )
    else:
        mock_exception_log.assert_not_called()


def test_sync_hubspot_deal_uai_order_no_tokens(mocker, settings, hubspot_order):
    """sync_hubspot_deal should not call task for UAI orders when no tokens available"""
    # Ensure no tokens are set
    settings.MITOL_HUBSPOT_API_PRIVATE_TOKEN = None
    if hasattr(settings, 'UAI_MITOL_HUBSPOT_API_PRIVATE_TOKEN'):
        delattr(settings, 'UAI_MITOL_HUBSPOT_API_PRIVATE_TOKEN')
    
    mock_sync = mocker.patch(
        "hubspot_sync.task_helpers.tasks.sync_deal_with_hubspot_targeted.apply_async"
    )
    mocker.patch("hubspot_sync.task_helpers.is_uai_order", return_value=True)
    
    sync_hubspot_deal(hubspot_order)
    mock_sync.assert_not_called()


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
    sync_hubspot_cart_add(user, product, is_uai_course=True)
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
