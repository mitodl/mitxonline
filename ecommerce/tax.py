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

from django.db.models import Q

from ecommerce.models import Product, TaxRate

CENTS = Decimal("0.01")


@dataclass(frozen=True)
class CalculatedTax:
    """
    The result of a tax calculation.

    Attributes:
    - tax_rate (TaxRate|None): the rate applied, or None if no tax is owed
    - rate (Decimal): the percentage applied (0 if no tax is owed)
    - taxable_amount (Decimal): the amount the tax was calculated on
    - tax_amount (Decimal): the tax owed, rounded to the cent
    - total (Decimal): taxable_amount plus tax_amount
    """

    tax_rate: TaxRate | None
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
        """Return True if any tax is owed."""

        return self.tax_amount > 0


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


def calculate_tax(amount: Decimal, tax_rate: TaxRate | None) -> CalculatedTax:
    """
    Calculate the tax owed on an amount at the given rate.

    Args:
    - amount (Decimal): the amount to tax
    - tax_rate (TaxRate|None): the rate to apply; None means no tax

    Returns:
    - CalculatedTax: the rate applied, the tax, and the total
    """

    amount = Decimal(amount)

    if tax_rate is None or amount <= 0:
        return CalculatedTax(
            tax_rate=None,
            rate=Decimal(0),
            taxable_amount=amount,
            tax_amount=Decimal("0.00"),
            total=amount,
        )

    tax_amount = (amount * tax_rate.tax_rate / Decimal(100)).quantize(
        CENTS, rounding=ROUND_HALF_UP
    )

    return CalculatedTax(
        tax_rate=tax_rate,
        rate=tax_rate.tax_rate,
        taxable_amount=amount,
        tax_amount=tax_amount,
        total=amount + tax_amount,
    )


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
