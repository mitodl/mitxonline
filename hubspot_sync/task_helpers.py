""" Task helper functions for ecommerce """
from django.conf import settings

from hubspot_sync import tasks


def sync_hubspot_user(user):
    """
    Trigger celery task to sync a User to Hubspot

    Args:
        user (User): The user to sync
    """
    if settings.MITOL_HUBSPOT_API_PRIVATE_TOKEN:
        tasks.sync_contact_with_hubspot.delay(user.id)


def sync_hubspot_deal(order):
    """
    Trigger celery task to sync an order to Hubspot if it has lines.
    Use a delay of 10 seconds to make sure state is updated first.

    Args:
        order (Order): The order to sync
    """
    if settings.MITOL_HUBSPOT_API_PRIVATE_TOKEN and order.lines.first() is not None:
        tasks.sync_deal_with_hubspot.apply_async(args=(order.id,), countdown=10)


def sync_hubspot_product(product):
    """
    Trigger celery task to sync a Product to Hubspot

    Args:
        product (Product): The product to sync
    """
    if settings.MITOL_HUBSPOT_API_PRIVATE_TOKEN:
        tasks.sync_product_with_hubspot.delay(product.id)
