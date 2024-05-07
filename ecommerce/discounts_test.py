import random
from decimal import Decimal

import pytest

from ecommerce.discounts import (
    DiscountType,
    DollarsOffDiscount,
    FixedPriceDiscount,
    PercentDiscount,
)
from ecommerce.factories import (
    DiscountFactory,
    ProductFactory,
    UnlimitedUseDiscountFactory,
)
from users.factories import UserFactory

pytestmark = [pytest.mark.django_db]


@pytest.fixture
def products():
    return ProductFactory.create_batch(5)


@pytest.fixture
def discounts():
    return DiscountFactory.create_batch(10)


@pytest.fixture
def users():
    """Creates a user"""
    return UserFactory.create_batch(2)


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
                    Decimal(product.price)
                    - (product.price * Decimal(discount.amount / 100)),
                    2,
                )
            else:
                discounted_price = None

            assert (  # noqa: PT018
                discounted_price >= 0
                and discounted_price == discount_logic.get_product_price(product)
            )


def test_discounted_price(products):
    """
    Tests the get_discounted_price call with some products to make sure the
    discount is applied successfully.
    """
    product = products[random.randrange(0, len(products), 1)]  # noqa: S311

    applied_discounts = [UnlimitedUseDiscountFactory.create()]

    manually_discounted_prices = DiscountType.for_discount(
        applied_discounts[0]
    ).get_product_price(product)

    test_discounted_price = DiscountType.get_discounted_price(
        applied_discounts, product
    )

    assert test_discounted_price == manually_discounted_prices
