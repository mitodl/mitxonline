import abc
from dataclasses import dataclass
from reversion.models import Version
from decimal import Decimal

from ecommerce.models import Discount, Product
from ecommerce.constants import (
    DISCOUNT_TYPE_PERCENT_OFF,
    DISCOUNT_TYPE_DOLLARS_OFF,
    DISCOUNT_TYPE_FIXED_PRICE,
)


def resolve_product_version(product: Product, product_version=None):
    """
    Resolves the specified version of the product. Specify None to indicate the
    current version. (This should probably move to the model.)

    Returns: Product; either the product you passed in or the version of the product
    you requested.
    """
    if product_version is None:
        return product

    versions = Version.objects.get_for_object(product)

    if versions.count() == 0:
        return product

    for test_version in versions.all():
        if test_version == product_version:
            return Product(
                id=test_version.field_dict["id"],
                content_type_id=test_version.field_dict["content_type_id"],
                object_id=test_version.field_dict["object_id"],
                price=test_version.field_dict["price"],
                description=test_version.field_dict["description"],
                is_active=test_version.field_dict["is_active"],
            )

    raise TypeError("Invalid product version specified")


@dataclass
class DiscountType(abc.ABC):
    _CLASSES = {}

    discount: Discount

    def __init_subclass__(cls, *, discount_type, **kwargs):
        super().__init_subclass__()

        if discount_type in cls._CLASSES:
            raise TypeError(f"{discount_type} already defined for DiscountType")

        cls.discount_type = discount_type
        cls._CLASSES[discount_type] = cls

    @classmethod
    def for_discount(cls, discount: Discount):
        DiscountTypeCls = cls._CLASSES[discount.discount_type]

        return DiscountTypeCls(discount)

    @staticmethod
    def get_discounted_price(discounts, product, *, product_version=None):
        """Return the price of the product with discounts"""
        if product_version is not None:
            product = resolve_product_version(product, product_version)

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
        # original spec had this tracking versions differently than the way it is now
        # need to build in some logic to check on reversion for a given version but it should be the latest one
        return self.get_product_version_price(product)

    @abc.abstractmethod
    def get_product_version_price(self, product: Product, version):
        pass


class PercentDiscount(DiscountType, discount_type=DISCOUNT_TYPE_PERCENT_OFF):
    def get_product_version_price(self, product: Product, version=None):

        version = resolve_product_version(product, version)

        return round(
            Decimal(version.price)
            - (version.price * Decimal(self.discount.amount / 100)),
            2,
        )


class DollarsOffDiscount(DiscountType, discount_type=DISCOUNT_TYPE_DOLLARS_OFF):
    def get_product_version_price(self, product: Product, version=None):
        version = resolve_product_version(product, version)

        if version.price < self.discount.amount:
            return Decimal(0)

        return version.price - self.discount.amount


class FixedPriceDiscount(DiscountType, discount_type=DISCOUNT_TYPE_FIXED_PRICE):
    def get_product_version_price(self, product: Product, version=None):
        return self.discount.amount
