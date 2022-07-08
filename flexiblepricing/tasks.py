"""
Periodic task that updates currency exchange rates.
"""
import requests

from flexiblepricing.api import update_currency_exchange_rate
from flexiblepricing.constants import get_currency_exchange_rate_api_request_url
from flexiblepricing.exceptions import (
    ExceededAPICallsException,
    UnexpectedAPIErrorException,
)
from flexiblepricing.models import FlexiblePrice
from flexiblepricing.mail_api import generate_flexible_price_email
from main.celery import app


@app.task
def sync_currency_exchange_rates():
    """
    Updates all CurrencyExchangeRate objects to reflect latest exchange rates from
    Open Exchange Rates API (https://openexchangerates.org/).
    """
    CURRENCY_EXCHANGE_RATE_API_REQUEST_URL = (
        get_currency_exchange_rate_api_request_url()
    )
    if not CURRENCY_EXCHANGE_RATE_API_REQUEST_URL:
        msg = (
            "Currency exchange API URL cannot be determined. "
            "Ensure that the OPEN_EXCHANGE_RATES_URL setting "
            "and the OPEN_EXCHANGE_RATES_APP_ID setting are both set."
        )
        raise RuntimeError(msg)
    resp = requests.get(CURRENCY_EXCHANGE_RATE_API_REQUEST_URL)
    resp_json = resp.json()
    # check specifically if maximum number of api calls per month has been exceeded
    if resp.status_code == 429:
        raise ExceededAPICallsException(resp_json["description"])
    if resp.status_code != 200:  # check for other API errors
        raise UnexpectedAPIErrorException(resp_json["description"])
    latest_rates = resp_json["rates"]
    update_currency_exchange_rate(latest_rates)


@app.task
def notify_flexible_price_status_change_email(flexible_price_id):
    """
    Sends email notifications when the flexible price status changes.
    """
    flexible_price = FlexiblePrice.objects.get(id=flexible_price_id)
    generate_flexible_price_email(flexible_price)
