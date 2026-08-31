"""Shared helpers for ecommerce tests."""

from decimal import Decimal

import reversion


def reprice_product(product, price=Decimal("100.00")):
    """
    Set a product's price under a new reversion revision, since order pricing
    reads the frozen product_version rather than the live row.

    Tests that apply a fixed-amount discount need this: the product factory's
    fuzzy price can land below the discount, and a discount that leaves the
    basket total unchanged is hidden from the payload.
    """
    with reversion.create_revision():
        product.price = price
        product.save()

    return product
