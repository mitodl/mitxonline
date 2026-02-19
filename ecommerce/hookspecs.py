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
