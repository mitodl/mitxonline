import abc
from dataclasses import dataclass
from decimal import Decimal

from ecommerce.constants import (
    DISCOUNT_TYPE_DOLLARS_OFF,
    DISCOUNT_TYPE_FIXED_PRICE,
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
    def for_discount(cls, discount: Discount):
        DiscountTypeCls = cls._CLASSES[discount.discount_type]

        return DiscountTypeCls(discount)

    @staticmethod
    def get_discounted_price(discounts, product):
        """Return the price of the product with discounts"""
        # apply discount to product using the best discount
        # in practice, orders will only have one discount
        # but JUST IN CASE this ever changes
        # we want to have this be deterministic
        price = product.price
        for discount in discounts:
            discount_cls = DiscountType.for_discount(discount)
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
    def get_product_version_price(self, product: Product):
        if product.price < self.discount.amount:
            return Decimal(0)

        return product.price - self.discount.amount


class FixedPriceDiscount(DiscountType, discount_type=DISCOUNT_TYPE_FIXED_PRICE):
    def get_product_version_price(self, product: Product):  # noqa: ARG002
        return Decimal(self.discount.amount)
