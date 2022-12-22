"""Signals for ecommerce models"""
from django.db.models.signals import post_save
from django.dispatch import receiver

from ecommerce.models import Order, Product
from hubspot_sync.task_helpers import sync_hubspot_deal, sync_hubspot_product


@receiver(post_save, sender=Product, dispatch_uid="product_post_save")
def sync_product(sender, instance, created, **kwargs):  # pylint:disable=unused-argument
    """
    Sync product to hubspot
    """
    sync_hubspot_product(instance)


@receiver(post_save, sender=Order, dispatch_uid="order_post_save")
def sync_order(sender, instance, created, **kwargs):  # pylint:disable=unused-argument
    """
    Sync order to hubspot
    """
    sync_hubspot_deal(instance)
