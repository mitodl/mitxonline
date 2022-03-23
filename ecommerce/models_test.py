import pytest
import random
from decimal import Decimal, getcontext
from mitol.common.utils import now_in_utc
import reversion

from users.factories import UserFactory

from ecommerce.models import (
    Order,
    DiscountRedemption,
    Basket,
    BasketItem,
    UserDiscount,
    BasketDiscount,
    PendingOrder,
    FulfilledOrder,
    RefundedOrder,
    Transaction,
)
from ecommerce import api
from ecommerce.factories import (
    ProductFactory,
    DiscountFactory,
    BasketFactory,
    OneTimeDiscountFactory,
    OneTimePerUserDiscountFactory,
    UnlimitedUseDiscountFactory,
    SetLimitDiscountFactory,
    BasketItemFactory,
)
from ecommerce.discounts import (
    DiscountType,
    PercentDiscount,
    FixedPriceDiscount,
    DollarsOffDiscount,
)
from ecommerce.views_test import user

pytestmark = [pytest.mark.django_db]


@pytest.fixture
def users():
    """Creates a user"""
    return UserFactory.create_batch(2)


@pytest.fixture()
def onetime_discount():
    return OneTimeDiscountFactory.create()


@pytest.fixture()
def onetime_per_user_discount():
    return OneTimePerUserDiscountFactory.create()


@pytest.fixture()
def unlimited_discount():
    return UnlimitedUseDiscountFactory.create()


@pytest.fixture()
def set_limited_use_discount():
    return SetLimitDiscountFactory.create()


@pytest.fixture()
def basket():
    return BasketFactory.create()


def perform_discount_redemption(user, discount):
    """Redeems a discount."""
    order = Order(purchaser=user, total_price_paid=10)
    order.save()

    redemption = DiscountRedemption(
        redeemed_discount=discount,
        redemption_date=now_in_utc(),
        redeemed_order=order,
        redeemed_by=user,
    )
    redemption.save()


def test_one_time_discount(user, onetime_discount):
    """
    Tests single-use discounts. These should be redeemable once, and then not
    again.
    """

    assert onetime_discount.check_validity(user) is True

    perform_discount_redemption(user, onetime_discount)

    assert onetime_discount.check_validity(user) is False


def test_one_time_per_user_discount(users, onetime_per_user_discount):
    """
    Tests one-per-user discounts. These should be redeemable once, by a specific
    user, and then not again for that user.
    """

    for user in users:
        assert onetime_per_user_discount.check_validity(user) is True

        perform_discount_redemption(user, onetime_per_user_discount)

        assert onetime_per_user_discount.check_validity(user) is False


def test_unlimited_discounts(users, unlimited_discount):
    """
    Tests unlimited discounts. These should always be applicable, so we just run
    the discount through each of the users returned by the factory a random
    number of times. They should all be redeemable.
    """

    for user in users:
        for i in range(random.randrange(1, 15, 1)):
            assert unlimited_discount.check_validity(user) is True

            perform_discount_redemption(user, unlimited_discount)

            assert unlimited_discount.check_validity(user) is True


def test_set_limit_discount_single_user(user, set_limited_use_discount):
    """
    Tests discounts with a set number of redemptions. Just repeatedly apply the
    discount until it fails. This works with a single user; there's a separate
    test for multiple users.
    """

    for i in range(set_limited_use_discount.max_redemptions):
        assert set_limited_use_discount.check_validity(user) is True

        perform_discount_redemption(user, set_limited_use_discount)

    assert set_limited_use_discount.check_validity(user) is False


def test_set_limit_discount_multiple_users(users, set_limited_use_discount):
    """
    Tests discounts with a set number of redemptions. Just repeatedly apply the
    discount until it fails. This works with multiple users - half go to one,
    half go to the other. There's a separate test for single users.
    """

    for user in users:
        for i in range(int(set_limited_use_discount.max_redemptions / 2)):
            assert set_limited_use_discount.check_validity(user) is True

            perform_discount_redemption(user, set_limited_use_discount)

    if set_limited_use_discount.max_redemptions % 2:
        perform_discount_redemption(user, set_limited_use_discount)

    assert set_limited_use_discount.check_validity(user) is False


def test_basket_discount_conversion(user, unlimited_discount):
    """
    Tests converting discounts applied to baskets to discounts applied to
    orders. This sets up a basket, then applies a discount to it, then creates
    an order and attempts to apply the order to the basket. The discount should
    be applied. Then, it tries that again; there shouldn't be a new redemption
    the second time around.

    Note that this just makes sure the discount is correctly attached - it
    doesn't test that the pricing logic is applied.
    """

    basket = Basket(user=user)
    basket.save()

    basket_discount = BasketDiscount(
        redemption_date=now_in_utc(),
        redeemed_by=user,
        redeemed_discount=unlimited_discount,
        redeemed_basket=basket,
    )
    basket_discount.save()

    order = Order(purchaser=user, total_price_paid=0)
    order.save()

    assert order.discounts.count() == 0

    converted_discount = basket_discount.convert_to_order(order)

    assert order.discounts.count() == 1

    reconverted_discount = basket_discount.convert_to_order(order)

    assert converted_discount == reconverted_discount


def test_order_refund():
    """
    Tests state change from fulfilled to refund. There should be a new
    Transaction record after the order has been refunded.
    """

    with reversion.create_revision():
        basket_item = BasketItemFactory.create()

    order = PendingOrder.create_from_basket(basket_item.basket)
    order.fulfill({"result": "Payment succeeded"})
    order.save()

    fulfilled_order = FulfilledOrder.objects.get(pk=order.id)

    assert fulfilled_order.transactions.count() == 1

    fulfilled_order.refund(fulfilled_order.total_price_paid, "Test refund", True)
    fulfilled_order.save()

    fulfilled_order.refresh_from_db()

    assert fulfilled_order.state == Order.STATE.REFUNDED
    assert fulfilled_order.transactions.count() == 2


def test_basket_order_equivalency(user, basket, unlimited_discount):
    """
    Creates a basket with a product and a discount, then converts it to an order
    and uses the Basket model's compare_to_order to make sure they're
    equivalent. Then, it changes the basket and tries again, which should fail.
    """

    basket_discount = BasketDiscount(
        redemption_date=now_in_utc(),
        redeemed_by=user,
        redeemed_discount=unlimited_discount,
        redeemed_basket=basket,
    )
    basket_discount.save()

    order = PendingOrder.create_from_basket(basket)

    order.save()

    assert basket.compare_to_order(order) is True

    BasketDiscount.objects.filter(redeemed_basket=basket).all().delete()
    basket.refresh_from_db()

    assert basket.compare_to_order(order) is False
