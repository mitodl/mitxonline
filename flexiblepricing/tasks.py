"""
Periodic task that updates currency exchange rates.
"""

import logging
from urllib.parse import quote_plus, urljoin
import uuid

import requests
from django.conf import settings

from flexiblepricing.api import determine_courseware_flexible_price_discount, get_ecommerce_products_by_courseware_name, update_currency_exchange_rate
from flexiblepricing.exceptions import (
    ExceededAPICallsException,
    UnexpectedAPIErrorException,
)
from flexiblepricing.mail_api import (
    generate_flexible_price_email,
    send_financial_assistance_request_denied_email,
)
from flexiblepricing.models import FlexiblePrice
from main.celery import app
from django.db import transaction


def get_open_exchange_rates_url(endpoint):
    """
    Helper function to generate the Open Exchange Rates API URL based on the
    supplied target endpoint.

    Args:
        - endpoint (string): the API to consume (latest.json, currencies.json, etc.)
    Returns:
        string - the constructed API
    """

    if settings.OPEN_EXCHANGE_RATES_URL and settings.OPEN_EXCHANGE_RATES_APP_ID:
        app_id = quote_plus(settings.OPEN_EXCHANGE_RATES_APP_ID)

        return urljoin(settings.OPEN_EXCHANGE_RATES_URL, f"{endpoint}?app_id={app_id}")
    else:
        msg = (
            "Currency exchange API URL cannot be determined. "
            "Ensure that the OPEN_EXCHANGE_RATES_URL setting "
            "and the OPEN_EXCHANGE_RATES_APP_ID setting are both set."
        )
        raise RuntimeError(msg)


@app.task
def sync_currency_exchange_rates():
    """
    Updates all CurrencyExchangeRate objects to reflect latest exchange rates from
    Open Exchange Rates API (https://openexchangerates.org/).
    """
    log = logging.getLogger()

    log.info("Loading currency code descriptions")

    currency_codes = {}
    resp = requests.get(get_open_exchange_rates_url("currencies.json"))  # noqa: S113
    if resp:
        resp_json = resp.json()
        if resp.status_code == 429:  # noqa: PLR2004
            raise ExceededAPICallsException(resp_json["description"])
        if resp.status_code != 200:  # noqa: PLR2004
            raise UnexpectedAPIErrorException(resp_json["description"])
        currency_codes = resp_json

    log.info("Updating exchange rate data")

    resp = requests.get(get_open_exchange_rates_url("latest.json"))  # noqa: S113
    resp_json = resp.json()
    # check specifically if maximum number of api calls per month has been exceeded
    if resp.status_code == 429:  # noqa: PLR2004
        raise ExceededAPICallsException(resp_json["description"])
    if resp.status_code != 200:  # check for other API errors  # noqa: PLR2004
        raise UnexpectedAPIErrorException(resp_json["description"])
    latest_rates = resp_json["rates"]

    log.info("Performing update task")

    update_currency_exchange_rate(latest_rates, currency_codes)


@app.task
def notify_flexible_price_status_change_email(flexible_price_id):
    """
    Sends email notifications when the flexible price status changes.
    """
    flexible_price = FlexiblePrice.objects.get(id=flexible_price_id)
    generate_flexible_price_email(flexible_price)


@app.task
def notify_financial_assistance_request_denied_email(
    flexible_price_id, email_subject, email_body
):
    """
    Sends email notification when the financial assistance request is denied.
    """
    flexible_price = FlexiblePrice.objects.get(id=flexible_price_id)
    send_financial_assistance_request_denied_email(
        flexible_price, email_subject, email_body
    )


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
    logger = logging.getLogger()
    if not getattr(instance, "courseware_object", None):
        logger.warning(
            "No courseware object found for FlexiblePrice ID: %s", instance.id
        )
        return None
    return instance.courseware_object


def _validate_course_run(courseware_object, instance_id):
    """Validate and return the first unexpired run if valid."""
    logger = logging.getLogger()
    try:
        first_run = courseware_object.first_unexpired_run
        if not first_run or not getattr(first_run, "courseware_id", None):
            logger.warning("Invalid course run for FlexiblePrice ID: %s", instance_id)
            return None
        else:
            return first_run
    except AttributeError:
        logger.exception("Course run validation failed for ID %s", instance_id)
        return None


def _get_valid_product_id(courseware_id, instance_id):
    """Retrieve and validate the product ID."""
    logger = logging.getLogger()
    try:
        products = get_ecommerce_products_by_courseware_name(courseware_id)
        if not products:
            logger.warning("No products found for FlexiblePrice ID: %s", instance_id)
            return None

        product_id = products[-1].get("id")
        if not product_id:
            logger.error("Invalid product structure for ID: %s", instance_id)
        else:
            return product_id
    except (requests.exceptions.RequestException, ValueError):
        logger.exception("Product retrieval failed for ID %s", instance_id)
        return None


def _calculate_discount_amount(courseware_object, instance):
    """Calculate and return the discount amount if valid."""
    logger = logging.getLogger()
    try:
        active_products = getattr(courseware_object, "active_products", None)
        if not active_products or not active_products.exists():
            logger.warning("No active products for FlexiblePrice ID: %s", instance.id)
            return None

        discount_result = determine_courseware_flexible_price_discount(
            active_products.first(), getattr(instance, "user", None)
        )

        if not discount_result or not hasattr(discount_result, "amount"):
            logger.error("Invalid discount result for ID: %s", instance.id)
            return None

        return float(discount_result.amount)
    except (AttributeError, ValueError, TypeError):
        logger.exception("Discount calculation failed for ID %s", instance.id)
        return None


def _create_discount_api_call(instance, product_id, amount):
    """Make the API call to create the discount."""
    logger = logging.getLogger()
    try:
        url = f"{settings.UNIFIED_ECOMMERCE_URL}/api/v0/payments/discounts/"
        api_key = settings.UNIFIED_ECOMMERCE_API_KEY

        discount_data = {
            "codes": str(uuid.uuid4()),
            "discount_type": instance.tier.discount.discount_type,
            "amount": amount,
            "payment_type": "financial-assistance",
            "users": [getattr(instance.user, "email", "")],
            "product": product_id,
            "automatic": True,
        }

        response = requests.post(
            url,
            json=discount_data,
            headers={"Authorization": f"Api-Key {api_key}"},
            timeout=10,
        )

        if response.status_code == 201:  # noqa: PLR2004
            logger.info("Discount created for ID: %s", instance.id)
        else:
            logger.error(
                "Discount creation failed for ID %s. Status: %s",
                instance.id,
                response.status_code,
            )
    except requests.exceptions.RequestException:
        logger.exception("API request failed for ID %s", instance.id)
    except (KeyError, ValueError, TypeError):
        logger.exception("Unexpected API error for ID %s", instance.id)

@app.task
def process_flexible_price_discount_task(instance_id):
    """
    Process the flexible price discount for the given instance.
    """
    log = logging.getLogger()
    instance = FlexiblePrice.objects.get(id=instance_id)
    try:
        with transaction.atomic():
            _process_flexible_price_discount(instance)
    except (ValueError, TypeError, AttributeError):
        log.exception("Error processing flexible price discount")
