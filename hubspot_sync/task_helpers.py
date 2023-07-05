""" Task helper functions for ecommerce """
import logging

from django.conf import settings

from hubspot_sync import tasks

# pylint:disable-bare-except

log = logging.getLogger(__name__)


def sync_hubspot_user(user):
    """
    Trigger celery task to sync a User to Hubspot

    Args:
        user (User): The user to sync
    """
    if settings.MITOL_HUBSPOT_API_PRIVATE_TOKEN:
        try:
            tasks.sync_contact_with_hubspot.delay(user)
        except:
            log.exception(
                "Exception calling sync_contact_with_hubspot for user %s", user.username
            )


def sync_hubspot_deal(order):
    """
    Trigger celery task to sync an order to Hubspot if it has lines.
    Use a delay of 10 seconds to make sure state is updated first.

    Args:
        order (Order): The order to sync
    """
    if settings.MITOL_HUBSPOT_API_PRIVATE_TOKEN and order.lines.first() is not None:
        try:
            tasks.sync_deal_with_hubspot.apply_async(args=(order.id,), countdown=10)
        except:
            log.exception(
                "Exception calling sync_deal_with_hubspot for order %d", order.id
            )


def sync_hubspot_line_by_line_id(line_id: int):
    """
    Trigger celery task to sync a Line to Hubspot.
    Use a delay of 10 seconds to make sure state is updated first.

    Args:
        line_id (int): The ID of the Line to sync with HubSpot
    """
    if settings.MITOL_HUBSPOT_API_PRIVATE_TOKEN and line_id is not None:
        try:
            tasks.sync_line_with_hubspot.apply_async(args=(line_id,), countdown=10)
        except:
            log.exception(
                "Exception calling sync_line_with_hubspot for line ID %d", line_id
            )


def sync_hubspot_product(product):
    """
    Trigger celery task to sync a Product to Hubspot

    Args:
        product (Product): The product to sync
    """
    if settings.MITOL_HUBSPOT_API_PRIVATE_TOKEN:
        try:
            tasks.sync_product_with_hubspot.delay(product.id)
        except:
            log.exception(
                "Exception calling sync_product_with_hubspot for product %d", product.id
            )
