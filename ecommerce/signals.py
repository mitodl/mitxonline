"""Signals for ecommerce models"""

from django.db.models.signals import post_save
from django.db.transaction import on_commit
from django.dispatch import receiver

from ecommerce.models import Product
from hubspot_sync.task_helpers import sync_hubspot_product


@receiver(post_save, sender=Product, dispatch_uid="product_post_save")
def sync_product(sender, instance, created, **kwargs):  # pylint:disable=unused-argument  # noqa: ARG001
    """
    Sync product to hubspot
    """
    on_commit(lambda: sync_hubspot_product(instance))
