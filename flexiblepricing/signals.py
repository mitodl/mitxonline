"""
Signals for mitxonline course certificates
"""

import logging
import uuid

import requests
from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from flexiblepricing.api import (
    determine_courseware_flexible_price_discount,
    get_ecommerce_products_by_courseware_name,
)
from flexiblepricing.constants import FlexiblePriceStatus
from flexiblepricing.models import FlexiblePrice

logger = logging.getLogger(__name__)


@receiver(
    post_save,
    sender=FlexiblePrice,
    dispatch_uid="flexibleprice_post_save",
)
def handle_flexible_price_save(
    sender,  # pylint: disable=unused-argument  # noqa: ARG001
    instance,
    created,  # pylint: disable=unused-argument  # noqa: ARG001
    **kwargs,  # pylint: disable=unused-argument  # noqa: ARG001
):
    """
    When a FlexiblePrice is saved.
    """
    if instance.status in (
        FlexiblePriceStatus.APPROVED,
        FlexiblePriceStatus.AUTO_APPROVED,
    ):
        with transaction.atomic():
            if not instance.courseware_object:
                logger.warning(
                    "No courseware object found for FlexiblePrice ID: %s",
                    instance.id
                )
                return

            if not instance.courseware_object.first_unexpired_run:
                logger.warning(
                    "No unexpired run found for FlexiblePrice ID: %s",
                    instance.id
                )
                return
            products = get_ecommerce_products_by_courseware_name(instance.courseware_object.first_unexpired_run.courseware_id)
            product_id = products[-1]["id"]

            # If there are no products, log a warning and return
            if not products:
                logger.warning(
                    "No products found for courseware object (FlexiblePrice ID: %s)",
                    instance.id,
                )
                return

            url = f"{settings.UNIFIED_ECOMMERCE_URL}/api/v0/payments/discounts/"

            # handle when there are no active products
            if not instance.courseware_object.active_products:
                logger.warning(
                    "No active products found for courseware object (FlexiblePrice ID: %s)",
                    instance.id,
                )
                return

            amount = determine_courseware_flexible_price_discount(
                instance.courseware_object.active_products.first(), instance.user
            ).amount

            # Discount data
            discount_data = {
                "codes": str(uuid.uuid4()),
                "discount_type": "fixed-price",
                "amount": float(amount),
                "payment_type": "financial-assistance",
                "users": [instance.user.email],
                "product": product_id,
                "automatic": True,
            }

            # Make POST request
            response = requests.post(  # noqa: S113
                url,
                json=discount_data,
                headers={
                    "Authorization": f"Api-Key {settings.UNIFIED_ECOMMERCE_API_KEY}"
                },
            )

            if response.status_code == 201:  # noqa: PLR2004
                logger.info(
                    "Discount created successfully for FlexiblePrice ID: %s. Response: %s",
                    instance.id,
                    response.json(),
                )
            else:
                logger.error(
                    "Error creating discount for FlexiblePrice ID: %s. Status: %s, Response: %s",
                    instance.id,
                    response.status_code,
                    response,
                )
