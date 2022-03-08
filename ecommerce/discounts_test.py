import pytest
import random
from decimal import Decimal, getcontext
from mitol.common.utils import now_in_utc

from users.factories import UserFactory

from reversion.models import Version

from ecommerce.models import Basket, BasketItem, UserDiscount, BasketDiscount
from ecommerce import api
from ecommerce.factories import (
    ProductFactory,
    DiscountFactory,
    OneTimeDiscountFactory,
    OneTimePerUserDiscountFactory,
    UnlimitedUseDiscountFactory,
    SetLimitDiscountFactory,
)
from ecommerce.discounts import (
    DiscountType,
    PercentDiscount,
    FixedPriceDiscount,
    DollarsOffDiscount,
)
from ecommerce.views_test import user
from ecommerce.models_test import unlimited_discount

pytestmark = [pytest.mark.django_db]


@pytest.fixture()
def products():
    return ProductFactory.create_batch(5)


@pytest.fixture()
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

            assert (
                discounted_price >= 0
                and discounted_price == discount_logic.get_product_price(product)
            )


def test_user_discount_application(user, unlimited_discount, products):
    """
    Creates a user discount (which should be applied automatically for a
    particular user), and then creates a basket for that particular user and
    applies the user discounts. The User Discount should be applied.
    """
    product = products[random.randrange(0, len(products), 1)]

    basket = Basket(user=user)
    basket.save()

    item = BasketItem(product=product, basket=basket, quantity=1)
    item.save()

    user_discount = UserDiscount(user=user, discount=unlimited_discount)
    user_discount.save()

    api.apply_user_discounts(user)

    assert BasketDiscount.objects.filter(redeemed_basket=basket).count() > 0


def test_discounted_price(products):
    """
    Tests the get_discounted_price call with some products to make sure the
    discount is applied successfully.
    """
    product = products[random.randrange(0, len(products), 1)]

    applied_discounts = [
        UnlimitedUseDiscountFactory.create(),
        UnlimitedUseDiscountFactory.create(),
    ]

    manually_discounted_prices = [
        DiscountType.for_discount(applied_discounts[0]).get_product_price(product),
        DiscountType.for_discount(applied_discounts[1]).get_product_price(product),
    ]

    test_discounted_price = DiscountType.get_discounted_price(
        applied_discounts, product
    )

    assert (
        test_discounted_price == manually_discounted_prices[0]
        or test_discounted_price == manually_discounted_prices[1]
    )
