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

                discounted_price = max(discounted_price, 0)
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


@pytest.mark.parametrize(
    ("discount_type", "product_price", "discount_amount", "expected_price"),
    [
        pytest.param("dollars-off", Decimal("39.33"), 10, Decimal("29.33")),
        pytest.param("dollars-off", Decimal("9.99"), 10, Decimal("0.00")),
        pytest.param("fixed-price", Decimal("100.00"), 42, Decimal("42.00")),
        pytest.param("fixed-price", Decimal("42.00"), 42, Decimal("42.00")),
        pytest.param("fixed-price", Decimal("39.33"), 42, Decimal("39.33")),
        pytest.param("percent-off", Decimal("39.33"), 25, Decimal("29.50")),
        pytest.param("percent-off", Decimal("19.99"), 33, Decimal("13.39")),
    ],
)
def test_discounted_price(
    discount_type, product_price, discount_amount, expected_price
):
    """
    Tests the get_discounted_price call with deterministic inputs.

    In particular, fixed-price discounts should be ignored when the fixed price
    is higher than the product price because get_discounted_price applies the
    best available price.
    """
    product = ProductFactory.create(price=product_price)

    applied_discounts = [
        UnlimitedUseDiscountFactory.create(
            discount_type=discount_type,
            amount=discount_amount,
        )
    ]

    manually_discounted_prices = min(
        DiscountType.for_discount(applied_discounts[0]).get_product_price(product),
        product.price,
    )

    test_discounted_price = DiscountType.get_discounted_price(
        applied_discounts, product
    )

    assert manually_discounted_prices == expected_price
    assert test_discounted_price == manually_discounted_prices


def test_discounted_price_uses_best_price_across_multiple_discounts():
    """The lowest valid price should win when multiple discounts are present."""
    product = ProductFactory.create(price=Decimal("100.00"))
    applied_discounts = [
        UnlimitedUseDiscountFactory.create(
            discount_type="dollars-off",
            amount=20,
        ),
        UnlimitedUseDiscountFactory.create(
            discount_type="fixed-price",
            amount=90,
        ),
        UnlimitedUseDiscountFactory.create(
            discount_type="percent-off",
            amount=25,
        ),
    ]

    discounted_prices = [
        DiscountType.for_discount(discount).get_product_price(product)
        for discount in applied_discounts
    ]

    assert DiscountType.get_discounted_price(applied_discounts, product) == min(
        discounted_prices + [product.price]
    )

