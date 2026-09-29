"""Tests for the Stripe webhook hookimpls."""

import pytest

from ecommerce.constants import (
    STRIPE_EVENT_CHARGE_REFUND_UPDATED,
    STRIPE_EVENT_CHECKOUT_SESSION_COMPLETED,
    STRIPE_EVENT_REFUND_UPDATED,
)
from ecommerce.fixtures import stripe_event
from ecommerce.hooks.stripe_webhooks import RefundEvents
from main.plugin_manager import get_plugin_manager


@pytest.mark.parametrize(
    ("event_type", "should_process"),
    [
        (STRIPE_EVENT_REFUND_UPDATED, True),
        (STRIPE_EVENT_CHARGE_REFUND_UPDATED, True),
        (STRIPE_EVENT_CHECKOUT_SESSION_COMPLETED, False),
        ("setup_intent.created", False),
    ],
)
def test_refund_webhooks(mocker, event_type, should_process):
    """Only refund events should be sent to refund processing."""

    mocked_process = mocker.patch(
        "ecommerce.api.process_stripe_refund_updated", return_value="processed"
    )
    event = stripe_event()
    event.type = event_type

    result = RefundEvents().refund_webhooks(event)

    if should_process:
        mocked_process.assert_called_once_with(event)
        assert result == "processed"
    else:
        mocked_process.assert_not_called()
        assert result is True


def test_refund_events_registered():
    """The refund hookimpl should be registered with the plugin manager."""

    pm = get_plugin_manager()

    assert any(isinstance(plugin, RefundEvents) for plugin in pm.get_plugins())
