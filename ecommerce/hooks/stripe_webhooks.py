"""Plugins for Stripe webhook processing."""

import logging

import pluggy
from stripe import Event

hookimpl = pluggy.HookimplMarker("mitxonline")
log = logging.getLogger(__name__)


class CheckoutSessionEvents:
    """
    Wrapper class for checkout session events.

    The event type should be checked here so the logic doesn't have to.
    """

    @hookimpl(specname="stripe_event", tryfirst=True)
    def log_event(self, event: Event):
        """Log the incoming Stripe event."""

        # Probably want to toggle this; Stripe's inbuilt logging is pretty good
        # so we might not want to continue to log things locally.

        from ecommerce.api import log_stripe_event  # noqa: PLC0415

        log_stripe_event(event)

    @hookimpl(specname="stripe_event")
    def checkout_webhooks(self, event: Event):
        """
        Call the function to process checkout events.

        This includes these events:
        - checkout.session.completed
        - checkout.session.expired
        """
        from ecommerce.api import (  # noqa: PLC0415
            process_stripe_checkout_completed,
            process_stripe_checkout_expired,
        )

        if event.type == "checkout.session.completed":
            return process_stripe_checkout_completed(event)

        if event.type == "checkout.session.expired":
            return process_stripe_checkout_expired(event)

        return None
