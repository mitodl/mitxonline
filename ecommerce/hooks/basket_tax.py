"""
Basket hook that works out the tax on the basket.

Runs after each basket change, by which time the BasketLocation hook has
recorded where the user is.
"""

import pluggy

hookimpl = pluggy.HookimplMarker("mitxonline")


class BasketTax:
    """Recalculate the tax on the basket's items."""

    @hookimpl
    def basket_post_update(self, request, basket, update):  # noqa: ARG002
        """Recalculate the basket's tax."""

        # ecommerce.api imports ecommerce.models, which imports the plugin
        # manager, which imports this module.
        from ecommerce.api import recalculate_basket_tax  # noqa: PLC0415

        recalculate_basket_tax(basket)
