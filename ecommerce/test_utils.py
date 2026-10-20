"""Test utilities for ecommerce."""

import reversion

from ecommerce.factories import LineFactory, OrderFactory
from ecommerce.models import OrderStatus

def make_order_for_product(user, product, *, status=OrderStatus.FULFILLED):
    """Makes an order for a given product, using the factories."""
    product_version = reversion.models.Version.objects.get_for_object(product).first()
    order = OrderFactory.create(purchaser=user)
    LineFactory.create(product_version=product_version, purchased_object=product.purchasable_object, order=order)

    order.state = OrderStatus.FULFILLED
    order.save()

    return order
