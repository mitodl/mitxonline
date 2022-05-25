"""Flexible price apis"""
import csv
from collections import namedtuple
import logging

from django.db import transaction

from flexiblepricing.constants import INCOME_THRESHOLD_FIELDS, COUNTRY, INCOME
from flexiblepricing.exceptions import CountryIncomeThresholdException
from flexiblepricing.models import CountryIncomeThreshold, CurrencyExchangeRate

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
