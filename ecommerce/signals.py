"""Signals for ecommerce models"""

from django.db.models import QuerySet
from django.db.models.signals import post_delete, post_save
from django.db.transaction import on_commit
from django.dispatch import receiver

from ecommerce.models import Basket, BasketDiscount, Product
from hubspot_sync.task_helpers import sync_hubspot_product


@receiver(post_save, sender=Product, dispatch_uid="product_post_save")
def sync_product(sender, instance, created, **kwargs):  # pylint:disable=unused-argument  # noqa: ARG001
    """
    Sync product to hubspot
    """
    on_commit(lambda: sync_hubspot_product(instance))


@receiver(post_save, sender=BasketDiscount, dispatch_uid="basket_discount_post_save")
@receiver(
    post_delete, sender=BasketDiscount, dispatch_uid="basket_discount_post_delete"
)
def recalculate_tax_for_discount_change(sender, instance, **kwargs):  # noqa: ARG001
    """
    Recalculate the basket's tax when a discount is added, changed or removed.

    Tax is charged on the discounted price, and discounts are attached to
    baskets in many places (coupon redemption, financial assistance, B2B,
    verified program purchases), so this catches all of them.
    """
    from ecommerce.api import recalculate_basket_tax  # noqa: PLC0415

    # A delete that cascades from something else (the basket, or its user)
    # takes the basket's items with it, so there's nothing to re-tax - and
    # re-taxing would write tax rows for items about to be deleted.
    origin = kwargs.get("origin")
    if origin is not None and not (
        isinstance(origin, BasketDiscount)
        or (isinstance(origin, QuerySet) and origin.model is BasketDiscount)
    ):
        return

    basket = Basket.objects.filter(pk=instance.redeemed_basket_id).first()
    if basket is not None:
        recalculate_basket_tax(basket)
