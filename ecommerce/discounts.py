import abc
from dataclasses import dataclass
from decimal import Decimal

from ecommerce.constants import (
    DISCOUNT_TYPE_DOLLARS_OFF,
    DISCOUNT_TYPE_FIXED_PRICE,
    DISCOUNT_TYPE_PAID_AMOUNT_OFF,
    DISCOUNT_TYPE_PERCENT_OFF,
)
from ecommerce.models import Discount, Product


def product_from_version(version):
    """Reconstruct a Product from its reversion Version's serialized data."""
    if version is None:
        return None
    field_dict = version.field_dict
    return Product(
        id=field_dict["id"],
        content_type_id=field_dict["content_type_id"],
        object_id=field_dict["object_id"],
        price=field_dict["price"],
        description=field_dict["description"],
        is_active=field_dict["is_active"],
    )


@dataclass
class DiscountType(abc.ABC):
    _CLASSES = {}

    discount: Discount

    def __init_subclass__(cls, *, discount_type, **kwargs):
        super().__init_subclass__()

        if discount_type in cls._CLASSES:
            raise TypeError(f"{discount_type} already defined for DiscountType")  # noqa: EM102

        cls.discount_type = discount_type
        cls._CLASSES[discount_type] = cls

    @classmethod
    def for_discount(
        cls, discount: Discount, *, resolved_amount: Decimal | None = None
    ):
        DiscountTypeCls = cls._CLASSES[discount.discount_type]

        if resolved_amount is None:
            return DiscountTypeCls(discount)
        # Only PaidAmountOffDiscount declares the field. Any other type raises
        # TypeError here, which is right: a resolved amount for a percent-off
        # discount means the caller keyed its mapping to the wrong discount.
        return DiscountTypeCls(discount, resolved_amount=resolved_amount)

    @staticmethod
    def get_discounted_price(
        discounts, product, *, resolved_amounts: dict[int, Decimal] | None = None
    ):
        """Return the price of the product with discounts"""
        # apply discount to product using the best discount
        # in practice, orders will only have one discount
        # but JUST IN CASE this ever changes
        # we want to have this be deterministic
        price = product.price
        resolved_amounts = resolved_amounts or {}
        for discount in discounts:
            discount_cls = DiscountType.for_discount(
                discount, resolved_amount=resolved_amounts.get(discount.id)
            )
            price = min(discount_cls.get_product_price(product), price)

        return price

    def get_product_price(self, product: Product):
        return self.get_product_version_price(product)

    @abc.abstractmethod
    def get_product_version_price(self, product: Product):
        pass


class PercentDiscount(DiscountType, discount_type=DISCOUNT_TYPE_PERCENT_OFF):
    def get_product_version_price(self, product: Product):
        return round(
            Decimal(product.price)
            - (product.price * Decimal(self.discount.amount / 100)),
            2,
        )


class DollarsOffDiscount(DiscountType, discount_type=DISCOUNT_TYPE_DOLLARS_OFF):
    @property
    def amount_off(self) -> Decimal:
        return Decimal(self.discount.amount)

    def get_product_version_price(self, product: Product):
        return max(Decimal(0), Decimal(product.price) - self.amount_off)


class FixedPriceDiscount(DiscountType, discount_type=DISCOUNT_TYPE_FIXED_PRICE):
    def get_product_version_price(self, product: Product):  # noqa: ARG002
        return Decimal(self.discount.amount)


@dataclass
class PaidAmountOffDiscount(
    DollarsOffDiscount, discount_type=DISCOUNT_TYPE_PAID_AMOUNT_OFF
):
    """
    Dollars-off by the amount the learner paid for a qualifying prior purchase.

    The amount is resolved outside this module and injected via
    resolved_amounts; without one nothing comes off, so an unresolved discount
    can never undercharge. The discount's own stored amount is always 0.
    """

    # Computed by the caller and injected, because this layer must stay
    # user-blind and query-free: Line.compute_discounted_unit_price prices an
    # unsaved Product rebuilt from a reversion Version, so a query from here
    # would read the current row, not the historical one.
    resolved_amount: Decimal | None = None

    @property
    def amount_off(self) -> Decimal:
        if self.resolved_amount is None:
            return Decimal(0)

        return self.resolved_amount
