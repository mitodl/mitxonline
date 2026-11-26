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

from django.db.models import CharField, OuterRef, Q, Subquery
from django.db.models.functions import Cast
from reversion.models import Version

from ecommerce.models import Product, TaxRate

CENTS = Decimal("0.01")

# The fields a tax rate's version must match for it to be the rate applied.
VERSIONED_FIELDS = (
    "country_code",
    "subdivision_1_code",
    "subdivision_2_code",
    "tax_rate",
    "tax_rate_name",
    "is_active",
)


class TaxRateVersionError(Exception):
    """
    Raised when a saved tax rate has no saved version that matches it.

    This happens when tax is calculated inside the reversion revision that
    changes the rate: the revision isn't written until the block exits. Also
    raised if operating on a rate that was changed without using `.save` (and
    thus a new version wasn't committed), e.g. when using `.update`.
    """


@dataclass(frozen=True)
class CalculatedTax:
    """
    The result of a tax calculation.

    Attributes:
    - tax_rate (TaxRate|None): the rate applied, or None if the locale isn't taxed
    - tax_rate_version (Version|None): the version of the rate applied, for
      records to point at; None if no tax is owed or the rate is unsaved
    - rate (Decimal): the percentage applied (0 if no tax is owed)
    - taxable_amount (Decimal): the amount the tax was calculated on
    - tax_amount (Decimal): the tax owed, rounded to the cent
    - total (Decimal): taxable_amount plus tax_amount
    """

    tax_rate: TaxRate | None
    tax_rate_version: Version | None
    rate: Decimal
    taxable_amount: Decimal
    tax_amount: Decimal
    total: Decimal

    @property
    def tax_rate_name(self) -> str:
        """Return the name of the tax applied, or an empty string."""

        return self.tax_rate.tax_rate_name if self.tax_rate else ""

    @property
    def is_taxed(self) -> bool:
        """Return True if a tax rate applied, even if the tax came to zero."""

        return self.tax_rate is not None


def _with_version_id(rates):
    """
    Annotate rates with the ID of their newest version, as latest_version_id.

    The rate and its version ID then come from one statement, and so from one
    snapshot: a rate and its version are saved in the same transaction, so the
    version matches the row unless it is still in an open revision.
    """

    return rates.annotate(
        latest_version_id=Subquery(
            Version.objects.get_for_model(TaxRate)
            .filter(object_id=Cast(OuterRef("pk"), output_field=CharField()))
            .order_by("-pk")
            .values("pk")[:1]
        )
    )


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
    - TaxRate|None: the rate, or None if the locale isn't taxed. It carries
      latest_version_id, the ID of its newest version.
    """

    if not country_code:
        return None

    return (
        _with_version_id(TaxRate.objects)
        .filter(
            country_code=country_code.upper(),
            subdivision_1_code="",
            subdivision_2_code="",
        )
        .first()
    )


def calculate_tax(amount: Decimal, tax_rate: TaxRate | None) -> CalculatedTax:
    """
    Calculate the tax owed on an amount at the given rate.

    Args:
    - amount (Decimal): the amount to tax
    - tax_rate (TaxRate|None): the rate to apply; None means no tax. A saved
      rate is re-read along with its newest version ID, so the rate applied is
      the one the version records, even if the instance passed in is stale.

    Returns:
    - CalculatedTax: the rate applied, the tax, and the total

    Raises:
    - TaxRateVersionError: if the saved rate has no saved version matching it
    """

    if tax_rate is not None and tax_rate.pk is not None:
        tax_rate = _with_version_id(TaxRate.objects).get(pk=tax_rate.pk)

    return _calculate_tax(amount, tax_rate)


def _calculate_tax(amount: Decimal, tax_rate: TaxRate | None) -> CalculatedTax:
    """
    Calculate the tax owed on an amount at a rate read with _with_version_id.

    The rate isn't re-read, so it must be fresh from that query: a saved rate's
    latest_version_id is trusted to be its newest version as of that read.
    """

    # str() first so a float doesn't carry its binary error into the result.
    amount = Decimal(str(amount))

    if tax_rate is None:
        return CalculatedTax(
            tax_rate=None,
            tax_rate_version=None,
            rate=Decimal(0),
            taxable_amount=amount,
            tax_amount=Decimal("0.00"),
            total=amount,
        )

    tax_rate_version = None
    if tax_rate.pk is not None:
        # Versions are never changed once written, so loading this one in a
        # separate statement can't disagree with the row read with its ID.
        if tax_rate.latest_version_id is not None:
            tax_rate_version = Version.objects.get(pk=tax_rate.latest_version_id)

        if tax_rate_version is None or any(
            tax_rate_version.field_dict.get(field) != getattr(tax_rate, field)
            for field in VERSIONED_FIELDS
        ):
            msg = (
                f"Tax rate {tax_rate.pk} has no saved version matching it; "
                "calculate tax after the revision that saves it closes."
            )
            raise TaxRateVersionError(msg)

    # A free item in a taxed locale still records the rate, so a record can
    # tell "taxed at 0" apart from "not taxed".
    tax_amount = max(
        (amount * tax_rate.tax_rate / Decimal(100)).quantize(
            CENTS, rounding=ROUND_HALF_UP
        ),
        Decimal("0.00"),
    )

    return CalculatedTax(
        tax_rate=tax_rate,
        tax_rate_version=tax_rate_version,
        rate=tax_rate.tax_rate,
        taxable_amount=amount,
        tax_amount=tax_amount,
        total=amount + tax_amount,
    )


def calculate_tax_for_locale(
    amount: Decimal, country_code: str | None
) -> CalculatedTax:
    """
    Calculate the tax owed on an amount for a locale.

    The locale's active rate and its version are read in one statement and
    applied as read, so a rate deactivated, replaced, or moved to another
    locale in the meantime isn't charged, and no rate is missed while one is
    being replaced.

    Args:
    - amount (Decimal): the amount to tax
    - country_code (str|None): the ISO 3166-1 alpha-2 country code

    Returns:
    - CalculatedTax: the rate applied (if any), the tax, and the total

    Raises:
    - TaxRateVersionError: if the rate has no saved version matching it
    """

    # The rate was just read with its version ID, so it needn't be re-read.
    return _calculate_tax(amount, get_tax_rate_for_locale(country_code))


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

    if isinstance(product_id, int) or str(product_id).isdecimal():
        return Product.objects.get(pk=int(product_id))

    from courses.models import CourseRun, Program  # noqa: PLC0415

    # all_objects, so source runs are found here just as they are by ID.
    run_ids = CourseRun.all_objects.filter(courseware_id=product_id).values("pk")
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
    - TaxRateVersionError: if the rate has no saved version matching it
    """

    return get_product(product_id).calculate_tax_for_locale(country_code, price=price)
