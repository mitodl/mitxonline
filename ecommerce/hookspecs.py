"""Hookspecs for the ecommerce app."""
# ruff: noqa: ARG001

import pluggy

hookspec = pluggy.HookspecMarker("unified_ecommerce")


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
