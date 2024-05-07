"""
Periodic task that updates currency exchange rates.
"""

import logging
from urllib.parse import quote_plus, urljoin

import requests
from django.conf import settings

from flexiblepricing.api import update_currency_exchange_rate
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
