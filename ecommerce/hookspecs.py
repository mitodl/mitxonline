"""Hookspecs for the ecommerce app."""

import pluggy

hookspec = pluggy.HookspecMarker("mitxonline")


@hookspec
def discount_validate(basket, discount):
    """
    Validate a discount using the current basket and request.

    There are a handful of things that need to be checked when a discount is to
    be applied to a basket - the discount needs to be active, it should either
    not have product restrictions or should apply to the products in the basket,
    etc.

    Args:
    basket (Basket): the current basket
    discount (Discount): the discount under consideration

    Returns:
    - boolean; True if the discount is valid for the basket
    """


@hookspec(firstresult=True)
def process_transaction_line(line):
    """
    Perform post-order processing for a line item in a fulfilled order.

    Any action that needs to happen on a per-line basis should be implemented
    as a hook in this spec. This includes:
    - Creating enrollments for course runs
    - Creating enrollments for programs
    - Updating B2B contract membership

    This is a first result spec, so the first hook to return something besides
    None will stop further processing, so we can break out when we're done if
    we need to.

    Args:
    line (Line): the line to process

    Returns:
    - str|None: hook name that completed processing (or None to continue)
    """


@hookspec
def stripe_event(event):
    """
    Dispatch an event received from Stripe.

    The event data received includes the type of event that was triggered.
    Hookimpls should check this and process the event types they know about.
    This doesn't set firstresult so we can have global handlers and so we can
    scope the hookimpls to specific tasks.

    Implementations should return one of None, False, or Order. If the impl
    modifies an Order, it should return the Order, and the state of it should
    reflect the status of the operation that was taken. (In other words, if
    there was an error processing the order, the Order's state should be set
    to OrderState.ERRORED and it should return the Order.) If the impl
    encounters an error but doesn't modify the Order, then it should return
    False and do whatever logging that is necessary. If the impl finishes
    successfully but also doesn't modify the Order, then it should return
    True.

    If the impl hits a fatal error it should raise an exception so that further
    processing stops.

    Args:
    event (stripe._event.Event): The Stripe event to process.

    Returns:
    - True: success but no data
    - Order: the order that was updated in the step
    - False: error state
    """
