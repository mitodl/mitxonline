import pytest
import random
from decimal import Decimal, getcontext
from mitol.common.utils import now_in_utc
import reversion

from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError

from users.factories import UserFactory

from ecommerce.models import (
    Order,
    DiscountRedemption,
    Basket,
    BasketItem,
    UserDiscount,
    BasketDiscount,
    PendingOrder,
    Product,
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
    OrderFactory,
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
    order.fulfill({"result": "Payment succeeded", "transaction_id": "12345"})
    order.save()

    fulfilled_order = FulfilledOrder.objects.get(pk=order.id)

    assert fulfilled_order.transactions.count() == 1

    fulfilled_order.refund(
        # API response for refund doesn't have transaction_id, it has different id
        api_response_data={
            "id": "45678",
        },
        amount=fulfilled_order.total_price_paid,
        reason="Test refund",
        unenroll_learner=True,
    )
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


def test_product_delete_protection_inactive():
    """Test that deleting product(s) instead de-activates it"""
    single_product = ProductFactory.create()
    single_product.delete()

    # Assert single product delete
    assert Product.all_objects.filter(is_active=False).count() == 1

    multiple_products = ProductFactory.create_batch(5)
    Product.objects.all().delete()

    # Assert multiple products delete (QuerySet)
    assert (
        Product.all_objects.filter(is_active=False).count()
        == len(multiple_products) + 1
    )  # Additional 1 from above


def test_product_multiple_active_for_single_purchasable_object():
    """Test that creating multiple Products with the same course/program
    and are active is not allowed"""
    first_product = ProductFactory.create()
    try:
        with transaction.atomic():
            ProductFactory.create(purchasable_object=first_product.purchasable_object)
        pytest.fail("Two active Products for the same purchasable_object were allowed.")
    except IntegrityError:
        pass


def test_order_update_reference_number(user):
    """Test when order is created/updated, reference_number is updated in db"""
    order = Order(purchaser=user, total_price_paid=10)
    order.save()

    assert order.reference_number == order._generate_reference_number()

    existing_order = Order.objects.get(pk=order.id)
    existing_order.reference_number = None
    existing_order.save()

    assert (
        existing_order.reference_number == existing_order._generate_reference_number()
    )


def test_duplicated_product_lines_validation(basket):
    """Test that creating multiple lines for the same product in the same order are deduped automatically"""

    with reversion.create_revision():
        products = ProductFactory.create_batch(2)

    basket_item = BasketItem(product=products[1], basket=basket, quantity=2)
    basket_item.save()
    order = PendingOrder.create_from_basket(basket)
    order.save()
    assert order.lines.count() == 1

    basket_item.delete()
    basket_item = BasketItem(product=products[0], basket=basket, quantity=1)
    basket_item.save()
    basket_item = BasketItem(product=products[1], basket=basket, quantity=1)
    basket_item.save()
    order = PendingOrder.create_from_basket(basket)
    order.save()
    assert order.lines.count() == 2


def test_create_transaction_with_no_transaction_id():
    """test that creating payment or refund transaction without transaction id in payment data will raise exception"""

    with pytest.raises(ValidationError):
        pending_order = OrderFactory.create(state=Order.STATE.PENDING)
        pending_order.fulfill({})
        pending_order.save()
    assert (
        Transaction.objects.filter(
            transaction_type="payment",
        ).count()
        == 0
    )

    fulfilled_order = OrderFactory.create(state=Order.STATE.FULFILLED)
    with pytest.raises(ValidationError):
        fulfilled_order.refund(
            api_response_data={},
            amount=fulfilled_order.total_price_paid,
            reason="Test refund",
            unenroll_learner=True,
        )
    assert (
        Transaction.objects.filter(
            transaction_type="refund",
        ).count()
        == 0
    )
