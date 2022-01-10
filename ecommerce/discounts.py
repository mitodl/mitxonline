import abc
from dataclasses import dataclass
from reversion.models import Version

from ecommerce.models import Discount, Product
from ecommerce.constants import (
    DISCOUNT_TYPE_PERCENT_OFF,
    DISCOUNT_TYPE_DOLLARS_OFF,
    DISCOUNT_TYPE_FIXED_PRICE,
)

"""
Resolves the specified version of the product. Specify < 0 to indicate the 
current version. (This should probably move to the model.)

Returns: the Product you passed in, or a dict of the product data for the version
indicated.
"""


def resolve_product_version(product: Product, version=-1):
    if version <= 0:
        return product

    versions = Version.objects.get_for_instance(product)

    if version > len(versions):
        raise IndexError(f"{version} invalid for this product")

    return versions[version].field_dict


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

    def get_product_price(self, product: Product):
        # original spec had this tracking versions differently than the way it is now
        # need to build in some logic to check on reversion for a given version but it should be the latest one
        return self.get_product_version_price(product, -1)

    @abc.abstractmethod
    def get_product_version_price(self, product: Product, version):
        pass


class PercentDiscount(DiscountType, discount_type=DISCOUNT_TYPE_PERCENT_OFF):
    def get_product_version_price(self, product: Product, version=-1):
        from decimal import Decimal

        version = resolve_product_version(product, version)

        return round(version.price * Decimal(self.discount.amount / 100), 2)


class DollarsOffDiscount(DiscountType, discount_type=DISCOUNT_TYPE_DOLLARS_OFF):
    def get_product_version_price(self, product: Product, version=-1):
        version = resolve_product_version(product, version)

        if version.price < self.discount.amount:
            return 0

        return version.price - self.discount.amount


class FixedPriceDiscount(DiscountType, discount_type=DISCOUNT_TYPE_FIXED_PRICE):
    def get_product_version_price(self, product: Product, version=-1):
        return self.discount.amount
