"""Flexible price apis"""
import csv
from collections import namedtuple
import logging
from datetime import datetime
import pytz

from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q

from main.settings import TIME_ZONE
from main.constants import DISALLOWED_CURRENCY_TYPES
from flexiblepricing.constants import (
    INCOME_THRESHOLD_FIELDS,
    COUNTRY,
    INCOME,
    DEFAULT_INCOME_THRESHOLD,
    FlexiblePriceStatus,
)
from flexiblepricing.exceptions import (
    CountryIncomeThresholdException,
    NotSupportedException,
)
from flexiblepricing.models import (
    CountryIncomeThreshold,
    CurrencyExchangeRate,
    FlexiblePriceTier,
    FlexiblePrice,
)

from courses.models import CourseRun, Course, ProgramRun

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


def get_ordered_eligible_coursewares(courseware):
    """
    Returns the courseware(s) eligible for a flexible pricing tier in order
    (program first, then course)
    """
    if isinstance(courseware, CourseRun):
        # recurse using the course run's course ;-)
        return get_ordered_eligible_coursewares(courseware.course)
    if isinstance(courseware, (Course, ProgramRun)) and courseware.program is not None:
        return [courseware.program, courseware]
    return [courseware]


def determine_tier_courseware(courseware, income):
    """
    Determines and returns the FlexiblePriceTier for a given income.

    If the courseware object is a program, this will look for tiers associated
    with that particular program. If it's a course, it'll look for tiers
    associated with the program first, then the course specified if there aren't
    any program tiers.

    Args:
        courseware (Program / Course): the Courseware to determine a Tier for
        income (numeric): the income of the User
    Returns:
        FlexiblePriceTier: the FlexiblePriceTier for the Courseware given the User's income
    """
    # To determine the tier for a user, find the set of every tier whose income threshold is
    # less than or equal to the income of the user. The highest tier out of that set will
    # be the tier assigned to the user.

    for eligible_courseware in get_ordered_eligible_coursewares(courseware):
        content_type = ContentType.objects.get_for_model(eligible_courseware)
        tier = (
            FlexiblePriceTier.objects.filter(
                current=True,
                income_threshold_usd__lte=income,
                courseware_content_type=content_type,
                courseware_object_id=eligible_courseware.id,
            )
            .order_by("-income_threshold_usd")
            .first()
        )

        if tier is not None:
            return tier

    message = (
        "$0-income-threshold Tier has not yet been configured for Courseware "
        "with id {courseware_id}.".format(courseware_id=courseware.id)
    )
    log.error(message)
    raise ImproperlyConfigured(message)


def determine_auto_approval(flexible_price, tier):
    """
    Takes income and country code and returns a boolean if auto-approved. Logs an error if the country of
    flexible_price does not exist in CountryIncomeThreshold.
    Args:
        flexible_price (FlexiblePrice): the flexibe price object to determine auto-approval
        tier (FlexiblePriceTier): the FlexiblePrice for the user's income level
    Returns:
        boolean: True if auto-approved, False if not
    """
    try:
        country_income_threshold = CountryIncomeThreshold.objects.get(
            country_code=flexible_price.country_of_income
        )
        income_threshold = country_income_threshold.income_threshold
    except CountryIncomeThreshold.DoesNotExist:
        log.error(
            "Country code %s does not exist in CountryIncomeThreshold for flexible price id %s",
            flexible_price.country_of_income,
            flexible_price.id,
        )
        income_threshold = DEFAULT_INCOME_THRESHOLD
    if tier.discount.amount == 0:
        # There is no discount so no reason to go through the financial aid workflow
        return True
    elif income_threshold == 0:
        # There is no income which we need to check the financial aid application
        return True
    else:
        return flexible_price.income_usd > income_threshold


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


def determine_courseware_flexible_price_discount(product, user):
    """
    Determine discount of a product

    The Product the learner is trying to purchase may have a course run or a
    program run attached to it. For this, if the product is for a program run,
    we look for a FlexiblePrice that is for the program. If the product is for
    a course run, we look for the course, or for the program that the course
    belongs to (if it belongs to one). This way, learners that apply for
    Flexible Pricing for an entire program get their discount on any course that
    is in the program.

    Args:
        product (Product): ecommerce Product of the cart
        user (User): the user of the cart
    Returns:
        discount: the discount provided in the flexible price tier
    """
    if not user.is_authenticated:
        return None

    for eligible_courseware in get_ordered_eligible_coursewares(
        product.purchasable_object
    ):
        content_type = ContentType.objects.get_for_model(eligible_courseware)
        flexible_price = (
            FlexiblePrice.objects.filter(
                courseware_content_type=content_type,
                courseware_object_id=eligible_courseware.id,
                user=user,
            )
            .filter(
                (
                    Q(tier__discount__activation_date=None)
                    | Q(
                        tier__discount__activation_date__lte=datetime.now(
                            pytz.timezone(TIME_ZONE)
                        )
                    )
                )
                & (
                    Q(tier__discount__expiration_date=None)
                    | Q(
                        tier__discount__expiration_date__gte=datetime.now(
                            pytz.timezone(TIME_ZONE)
                        )
                    )
                )
            )
            .first()
        )

        if (
            flexible_price
            and flexible_price.tier.current
            and flexible_price.status
            in (FlexiblePriceStatus.APPROVED, FlexiblePriceStatus.AUTO_APPROVED)
        ):
            return flexible_price.tier.discount

    return None


def is_courseware_flexible_price_approved(course_run, user):
    """
    Determines whether the user has a Flexible Price record that is approved for the course run.



    Args:
        course_run (CourseRun): The CourseRun associated with a potential Flexible Price.
        user (User): the user that potentially has a Flexible Price.
    Returns:
        boolean:True if the user has a Flexible Price record that is
                APPROVED or AUTO_APPROVED and assocaited with the CourseRun.
                False if the user does not have a Flexible Price that is APPROVED or AUTO_APPROVED
                and associated with the CourseRun.
    """

    for eligible_courseware in get_ordered_eligible_coursewares(course_run):
        content_type = ContentType.objects.get_for_model(eligible_courseware)
        flexible_price = FlexiblePrice.objects.filter(
            courseware_content_type=content_type,
            courseware_object_id=eligible_courseware.id,
            user=user,
        ).first()

        if (
            flexible_price
            and flexible_price.tier.current
            and flexible_price.status
            in (FlexiblePriceStatus.APPROVED, FlexiblePriceStatus.AUTO_APPROVED)
        ):
            return True

    return False

@transaction.atomic()
def update_currency_exchange_rate(rates, currency_descriptions):
    """
    Updates all CurrencyExchangeRate objects based on the latest rates.
    Args:
        rates (dict): latest exchange rates from Open Exchange Rates API
        currency_descriptions (dict): list of currency codes and descriptions
    Returns:
        None
    """
    codes = []

    log.info("Removing existing rates")

    CurrencyExchangeRate.objects.all().delete()

    for currency in rates:
        if currency in DISALLOWED_CURRENCY_TYPES:
            log.info(f"Skipping create on {currency}, in disallow list")
            continue

        description = (
            currency_descriptions[currency]
            if currency in currency_descriptions
            else None
        )

        CurrencyExchangeRate.objects.create(
            currency_code=currency,
            description=description,
            exchange_rate=rates[currency],
        )

        codes.append(currency)
