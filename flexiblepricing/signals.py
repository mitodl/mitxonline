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


@receiver(post_save, sender=FlexiblePrice, dispatch_uid="flexibleprice_post_save")
def handle_flexible_price_save(sender, instance, created, **kwargs):  # pylint: disable=unused-argument
    """Orchestrate the flexible price processing workflow."""
    if not _should_process_flexible_price(instance):
        return

    try:
        with transaction.atomic():
            _process_flexible_price_discount(instance)
    except (ValueError, TypeError, AttributeError) as e:
        _log_unexpected_error(instance, e)


def _should_process_flexible_price(instance) -> bool:
    """Check if the instance meets basic processing criteria."""
    if not hasattr(instance, 'status'):
        return False
    return instance.status in (FlexiblePriceStatus.APPROVED, FlexiblePriceStatus.AUTO_APPROVED)


def _process_flexible_price_discount(instance):
    """Handle the core discount creation logic."""
    courseware_object = _validate_courseware_object(instance)
    if not courseware_object:
        return

    course_run = _validate_course_run(courseware_object, instance.id)
    if not course_run:
        return

    product_id = _get_valid_product_id(course_run.courseware_id, instance.id)
    if not product_id:
        return

    discount_amount = _calculate_discount_amount(courseware_object, instance)
    if not discount_amount:
        return

    _create_discount_api_call(instance, product_id, discount_amount)


def _validate_courseware_object(instance):
    """Validate and return the courseware object if valid."""
    if not getattr(instance, 'courseware_object', None):
        logger.warning("No courseware object found for FlexiblePrice ID: %s", instance.id)
        return None
    return instance.courseware_object


def _validate_course_run(courseware_object, instance_id):
    """Validate and return the first unexpired run if valid."""
    try:
        first_run = courseware_object.first_unexpired_run
        if not first_run or not getattr(first_run, 'courseware_id', None):
            logger.warning("Invalid course run for FlexiblePrice ID: %s", instance_id)
            return None
        else:
            return first_run
    except AttributeError:
        logger.exception("Course run validation failed for ID %s", instance_id)
        return None


def _get_valid_product_id(courseware_id, instance_id):
    """Retrieve and validate the product ID."""
    try:
        products = get_ecommerce_products_by_courseware_name(courseware_id)
        if not products:
            logger.warning("No products found for FlexiblePrice ID: %s", instance_id)
            return None

        product_id = products[-1].get('id')
        if not product_id:
            logger.error("Invalid product structure for ID: %s", instance_id)
        else:
            return product_id
    except (requests.exceptions.RequestException, ValueError):
        logger.exception("Product retrieval failed for ID %s", instance_id)
        return None


def _calculate_discount_amount(courseware_object, instance):
    """Calculate and return the discount amount if valid."""
    try:
        active_products = getattr(courseware_object, 'active_products', None)
        if not active_products or not active_products.exists():
            logger.warning("No active products for FlexiblePrice ID: %s", instance.id)
            return None

        discount_result = determine_courseware_flexible_price_discount(
            active_products.first(),
            getattr(instance, 'user', None)
        )

        if not discount_result or not hasattr(discount_result, 'amount'):
            logger.error("Invalid discount result for ID: %s", instance.id)
            return None

        return float(discount_result.amount)
    except (AttributeError, ValueError, TypeError):
        logger.exception("Discount calculation failed for ID %s", instance.id)
        return None


def _create_discount_api_call(instance, product_id, amount):
    """Make the API call to create the discount."""
    try:
        url = f"{settings.UNIFIED_ECOMMERCE_URL}/api/v0/payments/discounts/"
        api_key = settings.UNIFIED_ECOMMERCE_API_KEY

        discount_data = {
            "codes": str(uuid.uuid4()),
            "discount_type": "fixed-price",
            "amount": amount,
            "payment_type": "financial-assistance",
            "users": [getattr(instance.user, 'email', '')],
            "product": product_id,
            "automatic": True,
        }

        response = requests.post(
            url,
            json=discount_data,
            headers={"Authorization": f"Api-Key {api_key}"},
            timeout=10
        )

        if response.status_code == 201:
            logger.info("Discount created for ID: %s", instance.id)
        else:
            logger.error("Discount creation failed for ID %s. Status: %s",
                       instance.id, response.status_code)
    except requests.exceptions.RequestException:
        logger.exception("API request failed for ID %s", instance.id)
    except (KeyError, ValueError, TypeError):
        logger.exception("Unexpected API error for ID %s", instance.id)


def _log_unexpected_error(instance, error):
    """Log unexpected errors at the top level."""
    logger.critical("Unhandled exception for ID %s: %s",
                   getattr(instance, 'id', 'unknown'), str(error))
