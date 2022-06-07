"""Flexible price apis"""
import csv
from collections import namedtuple
import logging

from django.core.exceptions import ImproperlyConfigured
from django.db import transaction

from flexiblepricing.constants import (
    INCOME_THRESHOLD_FIELDS,
    COUNTRY,
    INCOME,
    DEFAULT_INCOME_THRESHOLD,
)
from flexiblepricing.exceptions import (
    CountryIncomeThresholdException,
    NotSupportedException,
)
from flexiblepricing.models import (
    CountryIncomeThreshold,
    CurrencyExchangeRate,
    FlexiblePriceTier,
)

IncomeThreshold = namedtuple("IncomeThreshold", ["country", "income"])
log = logging.getLogger(__name__)


def parse_country_income_thresholds(csv_path):
    """
    Read CSV file and convert to IncomeThreshold object

    Args:
        csv_path(str o Path): Path to the CSV file

    Returns:
        list of IncomeThreshold, list:
    """
    with open(csv_path) as csv_file:
        reader = csv.DictReader(csv_file)

        header_row = reader.fieldnames
        if header_row:
            for field in INCOME_THRESHOLD_FIELDS:
                if field not in header_row:
                    raise CountryIncomeThresholdException(
                        f"Unable to find column header {field}"
                    )
        else:
            raise CountryIncomeThresholdException("Unable to find the header row")

        income_thresholds = [
            IncomeThreshold(country=row[COUNTRY], income=row[INCOME]) for row in reader
        ]
        return income_thresholds


def import_country_income_thresholds(csv_path):
    """
    Import country income threshold from the csv file

    Args:
        csv_path (str or Path): Path to a csv file
    """
    country_income_thresholds = parse_country_income_thresholds(csv_path)
    for income_threshold in country_income_thresholds:
        created = False
        try:
            country_income = CountryIncomeThreshold.objects.get(
                country_code=income_threshold.country
            )
        except CountryIncomeThreshold.DoesNotExist:
            country_income = CountryIncomeThreshold(
                country_code=income_threshold.country
            )
            created = True
        country_income.income_threshold = income_threshold.income
        country_income.save()

        if created:
            log.info(
                "Record created successfully for country=%s with income %s",
                country_income.country_code,
                country_income.income_threshold,
            )
        else:
            log.info(
                "Record updated successfully for country=%s with income %s",
                country_income.country_code,
                country_income.income_threshold,
            )


def determine_tier_courseware(courseware, income):
    """
    Determines and returns the FlexiblePriceTier for a given income.
    Args:
        courseware (Program / Course): the Courseware to determine a Tier for
        income (numeric): the income of the User
    Returns:
        TierProgram: the FlexiblePriceTier for the Courseware given the User's income
    """
    # To determine the tier for a user, find the set of every tier whose income threshold is
    # less than or equal to the income of the user. The highest tier out of that set will
    # be the tier assigned to the user.
    tiers_set = FlexiblePriceTier.objects.filter(
        current=True,
        income_threshold_usd__lte=income,
        courseware_object_id=courseware.id,
    )
    tier = tiers_set.order_by("-income_threshold_usd").first()
    if tier is None:
        message = (
            "$0-income-threshold Tier has not yet been configured for Courseware "
            "with id {courseware_id}.".format(courseware_id=courseware.id)
        )
        log.error(message)
        raise ImproperlyConfigured(message)
    return tier


def determine_auto_approval(flexibe_price, tier):
    """
    Takes income and country code and returns a boolean if auto-approved. Logs an error if the country of
    flexibe_price does not exist in CountryIncomeThreshold.
    Args:
        flexibe_price (FlexiblePrice): the flexibe price object to determine auto-approval
        tier (FlexiblePriceTier): the FlexiblePrice for the user's income level
    Returns:
        boolean: True if auto-approved, False if not
    """
    try:
        country_income_threshold = CountryIncomeThreshold.objects.get(
            country_code=flexibe_price.country_of_income
        )
        income_threshold = country_income_threshold.income_threshold
    except CountryIncomeThreshold.DoesNotExist:
        log.error(
            "Country code %s does not exist in CountryIncomeThreshold for flexible price id %s",
            flexibe_price.country_of_income,
            flexibe_price.id,
        )
        income_threshold = DEFAULT_INCOME_THRESHOLD
    if tier.discount.amount == 0:
        # There is no discount so no reason to go through the financial aid workflow
        return True
    elif income_threshold == 0:
        # There is no income which we need to check the financial aid application
        return True
    else:
        return flexibe_price.income_usd > income_threshold


def determine_income_usd(original_income, original_currency):
    """
    Take original income and original currency and converts income from the original currency
    to USD.
    Args:
        original_income (numeric): original income, in original currency (for a FlexiblePrice object)
        original_currency (str): original currency, a three-letter code
    Returns:
        float: the original income converted to US dollars
    """
    if original_currency == "USD":
        return original_income
    try:
        exchange_rate_object = CurrencyExchangeRate.objects.get(
            currency_code=original_currency
        )
    except CurrencyExchangeRate.DoesNotExist:
        raise NotSupportedException("Currency not supported")
    exchange_rate = exchange_rate_object.exchange_rate
    income_usd = original_income / exchange_rate
    return income_usd


@transaction.atomic
def update_currency_exchange_rate(latest_rates):
    """
    Updates all CurrencyExchangeRate objects based on the latest rates.
    Args:
        latest_rates (dict): latest exchange rates from Open Exchange Rates API
    Returns:
        None
    """
    rates = latest_rates.copy()  # So we don't modify the passed parameter
    currency_exchange_rates = CurrencyExchangeRate.objects.all()
    for currency_exchange_rate in currency_exchange_rates:
        if currency_exchange_rate.currency_code in rates:
            currency_exchange_rate.exchange_rate = rates.pop(
                currency_exchange_rate.currency_code
            )
            currency_exchange_rate.save()
        else:
            currency_exchange_rate.delete()
    for currency in rates:
        CurrencyExchangeRate.objects.create(
            currency_code=currency, exchange_rate=rates[currency]
        )
