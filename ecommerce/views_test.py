import pytest
import random

from ecommerce.models import BasketItem
from main.test_utils import assert_drf_json_equal
from django.urls import reverse
from django.conf import settings
import operator as op
import reversion
import uuid

from users.factories import UserFactory
from ecommerce.serializers import (
    ProductSerializer,
    BasketSerializer,
    BasketItemSerializer,
)
from ecommerce.models import Basket, BasketItem, Order

from ecommerce.factories import (
    ProductFactory,
    DiscountFactory,
    BasketItemFactory,
    BasketFactory,
)

pytestmark = [pytest.mark.django_db]


@pytest.fixture()
def products():
    with reversion.create_revision():
        return ProductFactory.create_batch(5)


@pytest.fixture()
def discounts():
    return DiscountFactory.create_batch(5)


@pytest.fixture
def user(db):
    """Creates a user"""
    return UserFactory.create()


@pytest.fixture(autouse=True)
def payment_gateway_settings():
    settings.MITOL_PAYMENT_GATEWAY_CYBERSOURCE_SECURITY_KEY = "Test Security Key"
    settings.MITOL_PAYMENT_GATEWAY_CYBERSOURCE_ACCESS_KEY = "Test Access Key"
    settings.MITOL_PAYMENT_GATEWAY_CYBERSOURCE_PROFILE_ID = uuid.uuid4()


def test_list_products(user_drf_client, products):
    resp = user_drf_client.get(reverse("products_api-list"), {"l": 10, "o": 0})
    resp_products = sorted(resp.json()["results"], key=op.itemgetter("id"))

    assert len(resp_products) == len(products)

    for product, resp_product in zip(products, resp_products):
        assert_drf_json_equal(resp_product, ProductSerializer(product).data)


def test_get_products(user_drf_client, products):
    product = products[random.randrange(0, len(products))]

    resp = user_drf_client.get(
        reverse("products_api-detail", kwargs={"pk": product.id})
    )

    assert_drf_json_equal(resp.json(), ProductSerializer(product).data)


def test_get_basket(user_drf_client, user):
    """Test the view that returns a state of Basket"""
    basket = BasketFactory.create(user=user)
    BasketItemFactory.create(basket=basket)
    resp = user_drf_client.get(
        reverse("basket-detail", kwargs={"username": user.username})
    )
    assert_drf_json_equal(resp.json(), BasketSerializer(basket).data)


def test_get_basket_items(user_drf_client, user):
    """Test the view that returns a list of BasketItems in a Basket"""
    basket = BasketFactory.create(user=user)
    basket_item = BasketItemFactory.create(basket=basket)
    basket_item_2 = BasketItemFactory.create(basket=basket)

    # this item belongs to another basket, and should not be in the response
    BasketItemFactory.create()
    resp = user_drf_client.get("/api/baskets/{}/items".format(basket.id), follow=True)
    basket_info = resp.json()
    assert len(basket_info) == 2
    assert_drf_json_equal(
        resp.json(),
        [
            BasketItemSerializer(basket_item).data,
            BasketItemSerializer(basket_item_2).data,
        ],
    )


def test_delete_basket_item(user_drf_client, user):
    """Test the view to delete item from the basket"""
    basket_item = BasketItemFactory.create(basket__user=user)
    basket = basket_item.basket
    assert basket.basket_items.count() == 1
    user_drf_client.delete(
        "/api/baskets/{}/items/{}/".format(user.username, basket_item.id),
        content_type="application/json",
    )
    assert BasketItem.objects.filter(basket=basket).count() == 0


def test_add_basket_item(user_drf_client, user):
    """Test the view to add a new item into the Basket"""
    new_product = ProductFactory.create()
    basket = BasketFactory.create(user=user)
    BasketItemFactory.create(basket=basket)
    assert BasketItem.objects.filter(basket__user=user).count() == 1

    user_drf_client.post(
        "/api/baskets/{}/items/".format(basket.id),
        data={"product": new_product.id},
        follow=True,
    )
    assert BasketItem.objects.filter(basket__user=user).count() == 2


def create_basket(user, products):
    """
    Bootstraps a basket with a product in it for testing the discount
    redemption APIs
    TODO: this should probably just be a factory
    """
    basket = Basket(user=user)
    basket.save()

    basket_item = BasketItem(
        product=products[random.randrange(0, len(products))], basket=basket, quantity=1
    )
    basket_item.save()

    return basket


def test_redeem_discount(user, user_drf_client, products, discounts):
    """
    Bootstraps a basket (see create_basket) and then attempts to redeem a
    discount on it. Should get back a success message. (The API call returns an
    ID so this doesn't just do json_equal.)
    """
    basket = create_basket(user, products)

    assert basket is not None
    assert len(basket.basket_items.all()) > 0

    discount = discounts[random.randrange(0, len(discounts))]

    resp = user_drf_client.post(
        reverse("checkout_api-redeem_discount"), {"discount": discount.id}
    )

    assert "message" in resp.json()

    resp_json = resp.json()

    assert resp_json["message"] == "Discount applied"


def test_start_checkout(user, user_drf_client, products):
    """
    Hits the start checkout view, which should create an Order record
    and its associated line items.
    """
    basket = create_basket(user, products)

    resp = user_drf_client.post(reverse("checkout_api-start_checkout"))

    # if there's not a payload in here, something went wrong
    assert "payload" in resp.json()

    order = Order.objects.filter(purchaser=user).get()

    assert order.state == Order.STATE.PENDING
    assert order.lines.count() == basket.basket_items.count()


def test_cancel_transaction(user, user_drf_client, products):
    """
    Generates an order (using the API endpoint) and then cancels it using the endpoint.
    There shouldn't be any PendingOrders after that happens.
    """
    create_basket(user, products)

    resp = user_drf_client.post(reverse("checkout_api-start_checkout"))

    payload = resp.json()["payload"]

    # Load the pending order from the DB(factory) - should match the ref# in
    # the payload we get back

    pending_order = Order.objects.get(state=Order.STATE.PENDING, purchaser=user)

    assert pending_order.reference_number == payload["reference_number"]

    # This is kind of cheating - CyberSource will send back a payload that is
    # signed, but here we're just passing the payload as we got it back from
    # the start checkout call.

    resp = user_drf_client.get(reverse("checkout-cancel_checkout"), payload)

    assert_drf_json_equal(resp.json(), {"message": "Order cancelled"})

    cancelled_order = Order.objects.get(pk=pending_order.id)

    assert cancelled_order == pending_order
    assert cancelled_order.state == Order.STATE.CANCELED


def test_receipt(user, user_drf_client, products):
    """
    Generates an order (using the API endpoint) and then pretends it went OK.
    There shouldn't be any PendingOrders after that happens, and the receipt
    endpoint should return back a single PendingOrder that has been Fulfilled.
    """
    create_basket(user, products)

    resp = user_drf_client.post(reverse("checkout_api-start_checkout"))

    pending_order = Order.objects.get(state=Order.STATE.PENDING, purchaser=user)

    resp = user_drf_client.get(reverse("checkout-receipt"), resp.json()["payload"])

    assert len(resp.json()) == 1

    completed_order = Order.objects.get(pk=pending_order.id)

    assert completed_order.state == Order.STATE.FULFILLED
