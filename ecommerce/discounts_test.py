import pytest
from decimal import Decimal, getcontext

from ecommerce.factories import ProductFactory, DiscountFactory
from ecommerce.discounts import (
    DiscountType,
    PercentDiscount,
    FixedPriceDiscount,
    DollarsOffDiscount,
)

pytestmark = [pytest.mark.django_db]


@pytest.fixture()
def products():
    return ProductFactory.create_batch(5)


@pytest.fixture()
def discounts():
    return DiscountFactory.create_batch(10)


def test_discount_factory_generation(discounts):
    """
    Runs through discounts and makes sure all the ones that come out of the
    factory are recognizable by the test suite. (This is a sort of sanity
    check - if a new discount type gets added and the tests aren't updated, this
    test will fail.)
    """
    for discount in discounts:
        discount_logic = DiscountType.for_discount(discount)

        what_type = (
            type(discount_logic) is DollarsOffDiscount,
            type(discount_logic) is FixedPriceDiscount,
            type(discount_logic) is PercentDiscount,
        )

        assert any(what_type)


def test_discount_factory_adjustment(discounts, products):
    """
    Tests discounting products. This runs through each factory-generated
    product and applies all of the discounts that have been generated, then
    compares the discounted price to the discount generated in the test.
    """
    for product in products:
        for discount in discounts:
            discount_logic = DiscountType.for_discount(discount)

            if type(discount_logic) is DollarsOffDiscount:
                discounted_price = product.price - discount.amount

                if discounted_price < 0:
                    discounted_price = 0
            elif type(discount_logic) is FixedPriceDiscount:
                discounted_price = discount.amount
            elif type(discount_logic) is PercentDiscount:
                discounted_price = round(
                    product.price * Decimal(discount.amount / 100), 2
                )
            else:
                discounted_price = None

            assert (
                discounted_price > 0
                and discounted_price == discount_logic.get_product_price(product)
            )
