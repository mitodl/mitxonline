"""
Tax calculation for MITx Online.

This module is the one place that knows how tax is worked out, so the rules can
change (or be handed to an outside service) without touching the callers.

The current rule is the one xPRO uses: a single percentage rate, looked up by
country, applied to the price being paid. The result is rounded to the cent.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING

from django.db.models import Q

from ecommerce.models import Product, TaxRate
from location.constants import LOCATION_FLAG_TYPE_TAX
from location.models import LocationFlag

if TYPE_CHECKING:
    from reversion.models import Version

    from location.dataclasses import UserCalculatedLocation

CENTS = Decimal("0.01")


@dataclass(frozen=True)
class CalculatedTax:
    """
    The result of a tax calculation.

    Attributes:
    - tax_rate (TaxRate|None): the rate applied, if known (None if no tax is
      owed, or if the tax was worked out from a version alone)
    - tax_rate_version (Version|None): the version of the rate applied; the
      rate and name below come from it
    - rate (Decimal): the percentage applied (0 if no tax is owed)
    - tax_rate_name (str): the name of the tax applied ("" if none)
    - taxable_amount (Decimal): the amount the tax was calculated on
    - tax_amount (Decimal): the tax owed, rounded to the cent
    - total (Decimal): taxable_amount plus tax_amount
    """

    tax_rate: TaxRate | None
    tax_rate_version: Version | None
    rate: Decimal
    tax_rate_name: str
    taxable_amount: Decimal
    tax_amount: Decimal
    total: Decimal

    @property
    def is_taxed(self) -> bool:
        """Return True if a tax rate applied, even if the tax came to zero."""

        return self.tax_rate is not None or self.tax_rate_version is not None


def get_tax_rate_for_locale(
    country_code: str | None,
) -> TaxRate | None:
    """
    Return the active tax rate for a locale, if there is one.

    Only country-level rates are matched for now: a rate with a subdivision set
    is ignored, since we have no way to place the learner in a subdivision.

    Args:
    - country_code (str|None): the ISO 3166-1 alpha-2 country code

    Returns:
    - TaxRate|None: the rate, or None if the locale isn't taxed
    """

    if not country_code:
        return None

    return TaxRate.objects.filter(
        country_code=country_code.upper(),
        subdivision_1_code="",
        subdivision_2_code="",
    ).first()


def get_tax_rate_for_locations(
    locations: list[UserCalculatedLocation],
) -> TaxRate | None:
    """
    Return the tax rate to charge a user found at the given locations.

    A user is taxed for a country only if a "tax" LocationFlag for that country
    is set for them (the flag's rule decides which of their locations count),
    and the country has an active TaxRate.

    Args:
    - locations (list[UserCalculatedLocation]): where the user was found,
      e.g. Basket.user_locations

    Returns:
    - TaxRate|None: the rate, or None if the user isn't taxed
    """

    country_codes = {
        location.country_code for location in locations if location.country_code
    }

    if not country_codes:
        return None

    flags = LocationFlag.objects.filter(
        flag_type=LOCATION_FLAG_TYPE_TAX, country_code__in=country_codes
    ).order_by("country_code", "id")

    for flag in flags:
        if flag.evaluate(locations) and (
            tax_rate := get_tax_rate_for_locale(str(flag.country_code))
        ):
            return tax_rate

    return None


def calculate_tax_from_version(
    amount: Decimal,
    tax_rate_version: Version | None,
    *,
    tax_rate: TaxRate | None = None,
) -> CalculatedTax:
    """
    Calculate the tax owed on an amount at the rate a TaxRate version records.

    Working from the version, rather than the live row, means the rate charged
    is always the one the version says, even if the rate has since changed.

    Args:
    - amount (Decimal): the amount to tax
    - tax_rate_version (Version|None): the version of the rate to apply; None
      means no tax
    - tax_rate (TaxRate|None): the rate the version belongs to, if loaded

    Returns:
    - CalculatedTax: the rate applied, the tax, and the total
    """

    # str() first so a float doesn't carry its binary error into the result.
    amount = Decimal(str(amount))

    if tax_rate_version is None:
        return CalculatedTax(
            tax_rate=None,
            tax_rate_version=None,
            rate=Decimal(0),
            tax_rate_name="",
            taxable_amount=amount,
            tax_amount=Decimal("0.00"),
            total=amount,
        )

    rate = Decimal(str(tax_rate_version.field_dict["tax_rate"]))

    # A free item in a taxed locale still records the rate, so a record can
    # tell "taxed at 0" apart from "not taxed".
    tax_amount = max(
        (amount * rate / Decimal(100)).quantize(CENTS, rounding=ROUND_HALF_UP),
        Decimal("0.00"),
    )

    return CalculatedTax(
        tax_rate=tax_rate,
        tax_rate_version=tax_rate_version,
        rate=rate,
        tax_rate_name=tax_rate_version.field_dict["tax_rate_name"],
        taxable_amount=amount,
        tax_amount=tax_amount,
        total=amount + tax_amount,
    )


def calculate_tax(amount: Decimal, tax_rate: TaxRate | None) -> CalculatedTax:
    """
    Calculate the tax owed on an amount at the given rate.

    The rate's current version is looked up and the tax worked out from it, so
    the result's rate and version always agree.

    Args:
    - amount (Decimal): the amount to tax
    - tax_rate (TaxRate|None): the rate to apply; None means no tax

    Returns:
    - CalculatedTax: the rate applied, the tax, and the total

    Raises:
    - ValueError: if the rate has no versions (see TaxRate.save)
    """

    if tax_rate is None:
        return calculate_tax_from_version(amount, None)

    version = tax_rate.current_version

    if version is None:
        msg = f"Tax rate {tax_rate.id} has no versions"
        raise ValueError(msg)

    return calculate_tax_from_version(amount, version, tax_rate=tax_rate)


def get_product(product_id: int | str) -> Product:
    """
    Look up an active product by ID, or by its courseware's readable ID.

    Args:
    - product_id (int|str): the product's ID, or the readable ID of the course
      run or program it sells

    Returns:
    - Product: the product

    Raises:
    - Product.DoesNotExist: if nothing matches
    """

    if isinstance(product_id, int) or str(product_id).isdigit():
        return Product.objects.get(pk=int(product_id))

    from courses.models import CourseRun, Program  # noqa: PLC0415

    run_ids = CourseRun.objects.filter(courseware_id=product_id).values("pk")
    program_ids = Program.objects.filter(readable_id=product_id).values("pk")

    return Product.objects.get(
        Q(
            content_type__app_label="courses",
            content_type__model="courserun",
            object_id__in=run_ids,
        )
        | Q(
            content_type__app_label="courses",
            content_type__model="program",
            object_id__in=program_ids,
        )
    )


def calculate_tax_for_product(
    product_id: int | str,
    country_code: str | None,
    *,
    price: Decimal | None = None,
) -> CalculatedTax:
    """
    Calculate the tax owed on a product for a locale.

    A convenience for callers that don't have the Product loaded yet.

    Args:
    - product_id (int|str): the product's ID, or its courseware's readable ID
    - country_code (str|None): the ISO 3166-1 alpha-2 country code
    - price (Decimal|None): the amount to tax; defaults to the product's price

    Returns:
    - CalculatedTax: the rate applied, the tax, and the total

    Raises:
    - Product.DoesNotExist: if the product can't be found
    """

    return get_product(product_id).calculate_tax_for_locale(country_code, price=price)


def summarize_taxes(tax_records) -> list[dict]:
    """
    Total up tax records by tax, for display.

    Records for the same tax (name and rate) are added together, so a basket or
    order with several items shows one line per tax.

    Args:
    - tax_records (Iterable[TaxRecord]): the records to total

    Returns:
    - list[dict]: one dict per tax, with tax_rate_name, rate and tax_amount
    """

    totals = {}

    for record in tax_records:
        key = (record.tax_rate_name, record.rate)
        totals[key] = totals.get(key, Decimal("0.00")) + record.tax_amount

    return [
        {"tax_rate_name": name, "rate": rate, "tax_amount": amount}
        for (name, rate), amount in totals.items()
    ]
