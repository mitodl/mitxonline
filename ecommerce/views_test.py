import pytest
import random

from main.test_utils import assert_drf_json_equal
from django.urls import reverse
from django.conf import settings
from django.forms.models import model_to_dict
import operator as op
import reversion
import uuid

from courses.factories import CourseRunFactory
from ecommerce.api import generate_checkout_payload
from ecommerce.discounts import DiscountType
from ecommerce.factories import (
    ProductFactory,
    DiscountFactory,
    BasketItemFactory,
    BasketFactory,
)
from ecommerce.models import Basket, BasketItem, Order, Discount, UserDiscount
from ecommerce.serializers import (
    ProductSerializer,
    BasketSerializer,
    BasketItemSerializer,
    DiscountSerializer,
)
from flexiblepricing.api import determine_courseware_flexible_price_discount
from flexiblepricing.constants import FlexiblePriceStatus
from flexiblepricing.factories import FlexiblePriceFactory, FlexiblePriceTierFactory
from users.factories import UserFactory


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


@pytest.fixture(autouse=True)
def mock_create_run_enrollments(mocker):
    return mocker.patch("courses.api.create_run_enrollments", autospec=True)


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
        reverse("checkout_api-redeem_discount"), {"discount": discount.discount_code}
    )

    assert "message" in resp.json()

    resp_json = resp.json()

    assert resp_json["message"] == "Discount applied"


def test_redeem_discount_with_higher_discount(
    user, user_drf_client, products, discounts
):
    """
    Bootstraps a basket (see create_basket) and then attempts to redeem a
    discount on it. Should get back a success message. (The API call returns an
    ID so this doesn't just do json_equal.)
    """
    product = products[random.randrange(0, len(products), 1)]
    course = product.purchasable_object.course
    tier = FlexiblePriceTierFactory.create(
        courseware_object=course,
        income_threshold_usd=25000,
        current=True,
        discount__amount=50,
    )
    flexible_price = FlexiblePriceFactory.create(
        income_usd=50000,
        country_of_income="US",
        user=user,
        courseware_object=course,
        status=FlexiblePriceStatus.APPROVED,
        tier=tier,
    )
    basket = create_basket(user, [product])

    assert basket is not None
    assert len(basket.basket_items.all()) > 0

    discount = discounts[random.randrange(0, len(discounts))]

    # check flexible price discount is applied
    resp = user_drf_client.get(reverse("checkout_api-cart"))
    resp_json = resp.json()
    assert (
        float(resp_json["discounts"][0]["redeemed_discount"]["amount"])
        == tier.discount.amount
    )

    resp = user_drf_client.post(
        reverse("checkout_api-redeem_discount"), {"discount": discount.discount_code}
    )
    assert "message" in resp.json()
    resp_json = resp.json()
    assert resp_json["message"] == "Discount applied"

    # check flexible price discount is applied
    flexible_discounted_price = DiscountType.get_discounted_price(
        [tier.discount], product
    )
    discounted_price = DiscountType.get_discounted_price([discount], product)
    resp = user_drf_client.get(reverse("checkout_api-cart"))
    resp_json = resp.json()

    resolved_discount_amount = (
        tier.discount.amount
        if flexible_discounted_price < discounted_price
        else discount.amount
    )

    assert (
        float(resp_json["discounts"][0]["redeemed_discount"]["amount"])
        == resolved_discount_amount
    )


def test_clear_discounts(user, user_drf_client, products, discounts):
    """
    Bootstraps a basket (see create_basket) and then attempts to redeem a
    discount on it, then clears it. Should get back a success message.
    """
    test_redeem_discount(user, user_drf_client, products, discounts)

    resp = user_drf_client.post(reverse("checkout_api-clear_discount"))

    assert resp.json() == "Discounts cleared"


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


def test_start_checkout_with_discounts(user, user_drf_client, products, discounts):
    """
    Applies a discount, then hits the start checkout view, which should create
    an Order record and its associated line items.
    """
    test_redeem_discount(user, user_drf_client, products, discounts)

    resp = user_drf_client.post(reverse("checkout_api-start_checkout"))

    # if there's not a payload in here, something went wrong
    assert "payload" in resp.json()

    order = Order.objects.filter(purchaser=user).get()

    assert order.state == Order.STATE.PENDING


@pytest.mark.parametrize(
    "decision, expected_redirect_url, expected_state, basket_exists",
    [
        ("CANCEL", reverse("cart"), Order.STATE.CANCELED, True),
        ("DECLINE", reverse("cart"), Order.STATE.DECLINED, True),
        ("ERROR", reverse("cart"), Order.STATE.ERRORED, True),
        ("REVIEW", reverse("user-dashboard"), Order.STATE.PENDING, True),
        ("ACCEPT", reverse("user-dashboard"), Order.STATE.FULFILLED, False),
    ],
)
def test_checkout_result(
    user,
    user_client,
    mocker,
    products,
    decision,
    expected_redirect_url,
    expected_state,
    basket_exists,
):
    """
    Generates an order (using the API endpoint) and then cancels it using the endpoint.
    There shouldn't be any PendingOrders after that happens.
    """
    mocker.patch(
        "mitol.payment_gateway.api.PaymentGateway.validate_processor_response",
        return_value=True,
    )
    basket = create_basket(user, products)

    resp = user_client.post(reverse("checkout_api-start_checkout"))

    payload = resp.json()["payload"]
    payload = {
        **{f"req_{key}": value for key, value in payload.items()},
        "decision": decision,
        "message": "payment processor message",
    }

    # Load the pending order from the DB(factory) - should match the ref# in
    # the payload we get back

    order = Order.objects.get(state=Order.STATE.PENDING, purchaser=user)

    assert order.reference_number == payload["req_reference_number"]

    # This is kind of cheating - CyberSource will send back a payload that is
    # signed, but here we're just passing the payload as we got it back from
    # the start checkout call.

    resp = user_client.post(reverse("checkout-result-callback"), payload)
    assert resp.status_code == 302
    assert resp.url == expected_redirect_url
    print(resp.cookies)

    order.refresh_from_db()

    if decision == "REVIEW":
        assert order.is_review

        # create a new basket and then resubmit for acceptance
        # basket should be extant afterwards
        # also create a new batch of products
        #  - otherwise it might select one that's being used in the old basket
        new_products = ProductFactory.create_batch(5)
        basket = create_basket(user, new_products)

        payload["decision"] = "ACCEPT"
        resp = user_client.post(reverse("checkout-result-callback"), payload)
        assert resp.status_code == 302
        assert resp.url == expected_redirect_url
    else:
        assert order.state == expected_state

    assert Basket.objects.filter(id=basket.id).exists() is basket_exists


@pytest.mark.parametrize(
    "cart_exists, cart_empty", [(True, False), (True, True), (False, True)]
)
@pytest.mark.parametrize("is_external_checkout", [True, False])
def test_checkout_product(
    user, user_client, cart_exists, cart_empty, is_external_checkout
):
    """
    Verifies that both /cart/add?product_id=? and /cart/add?course_id=? url adds the product to the cart
    and redirect to checkout
    """
    basket = BasketFactory.create() if cart_exists else None

    if not cart_empty:
        BasketItemFactory.create(basket=basket)

    product = ProductFactory.create()

    # Case 1: For in app checkout we have the product id at hand so this API is called with "product_id"
    # Case 2: For external checkout e.g. edX we only have Course Id so this api is called with "course_id" which is then
    # converted into product
    if is_external_checkout:
        course_run = CourseRunFactory.create()
        course_run.products.add(product)
        api_payload = {"course_id": course_run.courseware_id}
    else:
        api_payload = {"product_id": product.id}

    resp = user_client.get(reverse("checkout-product"), api_payload)

    assert resp.status_code == 302
    assert resp.url == reverse("cart")

    basket = Basket.objects.get(user=user)

    assert [item.product for item in basket.basket_items.all()] == [product]


def test_discount_rest_api(admin_drf_client, user_drf_client):
    """
    Checks that the admin REST API is only accessible by an admin
    user, and then checks basic functionality (list, retrieve, create).
    """
    discount = DiscountFactory.create()
    discount_payload = model_to_dict(discount)
    discount_payload["discount_code"] += "Test"
    discount_payload["id"] = None

    # checking permissions - these should return 403

    resp = user_drf_client.get(reverse("discounts_api-list"))
    assert resp.status_code == 403

    resp = user_drf_client.get(
        reverse("discounts_api-detail", kwargs={"pk": discount.id})
    )
    assert resp.status_code == 403

    resp = user_drf_client.post(reverse("discounts_api-list"), discount_payload)
    assert resp.status_code == 403

    resp = user_drf_client.patch(
        reverse("discounts_api-detail", kwargs={"pk": discount.id}), discount_payload
    )
    assert resp.status_code == 403

    resp = user_drf_client.delete(
        reverse("discounts_api-detail", kwargs={"pk": discount.id})
    )
    assert resp.status_code == 403

    # checking CRUD ops

    resp = admin_drf_client.get(reverse("discounts_api-list"))
    data = resp.json()

    assert resp.status_code == 200
    assert len(resp.json()) >= 1
    assert data["results"][0]["id"] == discount.id

    resp = admin_drf_client.get(
        reverse("discounts_api-detail", kwargs={"pk": discount.id})
    )
    data = resp.json()

    assert resp.status_code == 200
    assert data["id"] == discount.id

    resp = admin_drf_client.post(reverse("discounts_api-list"), discount_payload)
    data = resp.json()

    assert resp.status_code == 201
    assert data["discount_code"] == discount_payload["discount_code"]
    assert data["id"] is not None

    data["discount_code"] = "New Discount Code"
    discount_payload = data

    resp = admin_drf_client.patch(
        reverse("discounts_api-detail", kwargs={"pk": discount_payload["id"]}),
        discount_payload,
    )
    data = resp.json()

    assert resp.status_code == 200
    assert_drf_json_equal(resp.json(), DiscountSerializer(discount_payload).data)

    resp = admin_drf_client.delete(
        reverse("discounts_api-detail", kwargs={"pk": discount_payload["id"]})
    )

    assert resp.status_code == 204
    assert Discount.objects.filter(pk=discount_payload["id"]).count() == 0


def test_discount_redemptions_api(
    user, products, discounts, admin_drf_client, user_drf_client
):
    """
    Tests pulling redemeptions from a discount after submitting an order with
    one in it.
    """

    discount = discounts[random.randrange(0, len(discounts))]

    # permissions testing
    resp = user_drf_client.get(
        reverse("discounts_api-detail", kwargs={"pk": discount.id})
    )
    assert resp.status_code == 403

    resp = user_drf_client.get(f"/api/v0/discounts/{discount.id}/redemptions/")
    assert resp.status_code == 403

    # create basket with discount, then check for redemptions

    basket = create_basket(user, products)

    resp = user_drf_client.post(
        reverse("checkout_api-redeem_discount"), {"discount": discount.discount_code}
    )

    assert resp.status_code == 200

    resp = user_drf_client.post(reverse("checkout_api-start_checkout"))

    assert resp.status_code == 200

    resp = admin_drf_client.get(f"/api/v0/discounts/{discount.id}/redemptions/")
    assert resp.status_code == 200

    results = resp.json()
    assert results["count"] > 0


def test_user_discounts_api(user_drf_client, admin_drf_client, discounts, user):
    """
    Tests retrieving and creating user discounts via the API.
    """

    discount = discounts[random.randrange(0, len(discounts))]

    # permissions testing

    resp = user_drf_client.get(
        reverse("discounts_api-detail", kwargs={"pk": discount.id})
    )
    assert resp.status_code == 403

    resp = user_drf_client.get(f"/api/v0/discounts/{discount.id}/assignees/")
    assert resp.status_code == 403

    # create a user discount using the model first

    user_discount = UserDiscount(discount=discount, user=user)
    user_discount.save()

    resp = admin_drf_client.get(f"/api/v0/discounts/{discount.id}/assignees/")
    assert resp.status_code == 200

    data = resp.json()
    assert data["count"] > 0

    # try to post a user discount - that should also work
    discount = DiscountFactory.create()

    resp = admin_drf_client.post(
        reverse("userdiscounts_api-list"), {"discount": discount.id, "user": user.id}
    )
    assert resp.status_code >= 200 and resp.status_code < 300

    resp = admin_drf_client.get(f"/api/v0/discounts/{discount.id}/assignees/")
    assert resp.status_code == 200

    data = resp.json()
    assert data["count"] > 0
