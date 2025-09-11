"""Task helper functions for ecommerce"""

import logging

from django.conf import settings

from ecommerce.models import Order, Product
from hubspot_sync import tasks
from users.models import User

# pylint:disable-bare-except

log = logging.getLogger(__name__)


def sync_hubspot_user(user: User):
    """
    Trigger celery task to sync a User to Hubspot

    Args:
        user (User): The user to sync
    """
    log.info(f"🚀 sync_hubspot_user called for user {user.id} ({user.email})")
    if settings.MITOL_HUBSPOT_API_PRIVATE_TOKEN:
        try:
            log.info(f"✅ Queueing sync_contact_with_hubspot task for user {user.id}")
            tasks.sync_contact_with_hubspot.delay(user.id)
        except:  # noqa: E722
            log.exception(
                "❌ Exception calling sync_contact_with_hubspot for user %s",
                user.edx_username,
            )
    else:
        log.warning("⚠️  MITOL_HUBSPOT_API_PRIVATE_TOKEN not set - skipping user sync")


def sync_hubspot_deal(order: Order):
    """
    Trigger celery task to sync an order to Hubspot if it has lines.
    Use a delay of 10 seconds to make sure state is updated first.

    Args:
        order (Order): The order to sync
    """
    log.info(f"🚀 sync_hubspot_deal called for order {order.id} (state: {order.state})")
    if settings.MITOL_HUBSPOT_API_PRIVATE_TOKEN and order.lines.first() is not None:
        try:
            log.info(f"✅ Queueing sync_deal_with_hubspot task for order {order.id} with 10s delay")
            tasks.sync_deal_with_hubspot.apply_async(args=(order.id,), countdown=10)
        except:  # noqa: E722
            log.exception(
                "❌ Exception calling sync_deal_with_hubspot for order %d", order.id
            )
    else:
        if not settings.MITOL_HUBSPOT_API_PRIVATE_TOKEN:
            log.warning("⚠️  MITOL_HUBSPOT_API_PRIVATE_TOKEN not set - skipping order sync")
        else:
            log.info(f"⏭️  Order {order.id} has no lines - skipping sync")


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
        except:  # noqa: E722
            log.exception(
                "Exception calling sync_line_with_hubspot for line ID %d", line_id
            )


def sync_hubspot_product(product: Product):
    """
    Trigger celery task to sync a Product to Hubspot

    Args:
        product (Product): The product to sync
    """
    log.info(f"🚀 sync_hubspot_product called for product {product.id}")
    if settings.MITOL_HUBSPOT_API_PRIVATE_TOKEN:
        try:
            log.info(f"✅ Queueing sync_product_with_hubspot task for product {product.id}")
            tasks.sync_product_with_hubspot.delay(product.id)
        except:  # noqa: E722
            log.exception(
                "❌ Exception calling sync_product_with_hubspot for product %d", product.id
            )
    else:
        log.warning("⚠️  MITOL_HUBSPOT_API_PRIVATE_TOKEN not set - skipping product sync")
