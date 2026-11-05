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


@hookspec(firstresult=True)
def checkout_validate_basket(request, basket):
    """
    Check that the user can check out with what's in the basket.

    This is the first pre-flight step in generate_checkout_payload, and runs
    before any discounts are touched. Checks that are about the user and the
    products - blocked countries, duplicate purchases, runs that can't be
    upgraded - belong here.

    This is a first result spec: the first hook to return something stops
    processing, and checkout returns that result to the caller.

    Args:
    request (HttpRequest): the current request
    basket (Basket): the current basket

    Returns:
    - dict|None: an error payload (with an "error" key) to stop checkout, or
      None to continue

    Raises:
    - ExportComplianceDataError: if the user's profile can't be checked for
      export compliance. generate_checkout_payload turns this into a
      profile_incomplete payload, or re-raises it if asked to.
    """


@hookspec
def checkout_apply_discounts(request, basket):
    """
    Apply any discounts the basket should get automatically.

    This runs after checkout_validate_basket, and is skipped if the checkout
    is set to skip discount checks. Every hook runs; return values are ignored.

    Args:
    request (HttpRequest): the current request
    basket (Basket): the current basket
    """


@hookspec(firstresult=True)
def checkout_validate_discounts(request, basket):
    """
    Check that the discounts applied to the basket are valid.

    This runs after checkout_apply_discounts, and is skipped if the checkout
    is set to skip discount checks.

    This is a first result spec: the first hook to return something stops
    processing, and checkout returns that result to the caller.

    Args:
    request (HttpRequest): the current request
    basket (Basket): the current basket

    Returns:
    - dict|None: an error payload (with an "error" key) to stop checkout, or
      None to continue
    """


@hookspec(firstresult=True)
def checkout_finalize_basket(request, basket):
    """
    Perform the last checks on the basket before the order is created.

    This is the last pre-flight step, and always runs. Checks that depend on
    the final state of the basket, including its discounts, belong here.

    This is a first result spec: the first hook to return something stops
    processing, and checkout returns that result to the caller.

    Args:
    request (HttpRequest): the current request
    basket (Basket): the current basket

    Returns:
    - dict|None: an error payload (with an "error" key) to stop checkout, or
      None to continue
    """
