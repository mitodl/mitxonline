import operator as op
import random
import uuid
from datetime import datetime, timedelta

import freezegun
import pytest
import pytz
import reversion
from django.conf import settings
from django.forms.models import model_to_dict
from django.urls import reverse
from mitol.common.utils.datetime import now_in_utc
from rest_framework import status

from courses.factories import CourseRunFactory, ProgramRunFactory
from courses.models import PaidCourseRun
from ecommerce.constants import (
    DISCOUNT_TYPE_PERCENT_OFF,
    PAYMENT_TYPE_CUSTOMER_SUPPORT,
    PAYMENT_TYPE_FINANCIAL_ASSISTANCE,
    REDEMPTION_TYPE_ONE_TIME,
)
from ecommerce.discounts import DiscountType
from ecommerce.factories import (
    BasketFactory,
    BasketItemFactory,
    DiscountFactory,
    ProductFactory,
)
from ecommerce.models import (
    Basket,
    BasketItem,
    Discount,
    DiscountProduct,
    Order,
    PendingOrder,
    UserDiscount,
)
from ecommerce.serializers import (
    BasketItemSerializer,
    BasketSerializer,
    BasketWithProductSerializer,
    DiscountSerializer,
    ProductSerializer,
)
from flexiblepricing.constants import FlexiblePriceStatus
from flexiblepricing.factories import FlexiblePriceFactory, FlexiblePriceTierFactory
from main.constants import (
    USER_MSG_COOKIE_NAME,
    USER_MSG_TYPE_COURSE_NON_UPGRADABLE,
    USER_MSG_TYPE_ENROLL_DUPLICATED,
    USER_MSG_TYPE_PAYMENT_ACCEPTED_NOVALUE,
)
from main.settings import TIME_ZONE
from main.test_utils import assert_drf_json_equal
from main.utils import encode_json_cookie_value
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


def test_get_products_inactive(user_drf_client, products):
    """Test that Product detail API doesn't return data for inactive product"""
    product = products[random.randrange(0, len(products))]
    product.is_active = False
    product.save()

    resp = user_drf_client.get(
        reverse("products_api-detail", kwargs={"pk": product.id})
    )

    assert_drf_json_equal(resp.json(), {"detail": "Not found."})


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


def create_basket_with_product(user, product):
    """
    Bootstraps a basket with a specific product in it
    """
    basket = Basket(user=user)
    basket.save()

    basket_item = BasketItem(product=product, basket=basket, quantity=1)
    basket_item.save()

    return basket


@pytest.mark.parametrize(
    ["try_flex_pricing_discount", "try_whitespace"],
    [
        [True, False],
        [False, True],
        [True, True],
    ],
)
def test_redeem_discount(
    user,
    user_drf_client,
    products,
    discounts,
    try_flex_pricing_discount,
    try_whitespace,
):
    """
    Bootstraps a basket (see create_basket) and then attempts to redeem a
    discount on it. Should get back a success message. (The API call returns an
    ID so this doesn't just do json_equal.)

    The try_flex_pricing_discount sets whether or not the discount should be
    flagged to be used with a Flexible Pricing tier. If it is, then the
    redemption attempt should fail.

    The try_whitespace flag sets whether or not the discount should have some
    whitespace appended/prepended to it - the redemption code should strip this
    and the code should apply successfully.
    """
    basket = create_basket(user, products)

    assert basket is not None
    assert len(basket.basket_items.all()) > 0

    discount = discounts[random.randrange(0, len(discounts))]

    if try_flex_pricing_discount:
        discount.payment_type = PAYMENT_TYPE_FINANCIAL_ASSISTANCE
        discount.save()
        discount.refresh_from_db()

    if try_whitespace:
        # limit the discount_code to 47 so we can shove some blank characters in
        discount.discount_code = discount.discount_code[0:45]
        discount.discount_code = f"   {discount.discount_code}  "[0:50]

    resp = user_drf_client.post(
        reverse("checkout_api-redeem_discount"), {"discount": discount.discount_code}
    )

    resp_json = resp.json()

    if try_flex_pricing_discount:
        assert "not found" in resp_json
    else:
        assert "message" in resp_json
        assert resp_json["message"] == "Discount applied"


@pytest.mark.parametrize("try_product_discount", [True, False])
def test_redeem_product_discount(
    user, user_drf_client, products, discounts, try_product_discount
):
    """
    Bootstraps a basket (see create_basket) and then attempts to redeem a
    discount on it that is linked to an existing product. The result depends
    on try_product_discount.

    The try_product_discount parameter sets whether or not the discount should
    apply to the product that gets generated. If True, the discount application
    should succeed. If False, it won't.
    """
    basket = create_basket(user, products)

    assert basket is not None
    assert len(basket.basket_items.all()) > 0

    discount = discounts[random.randrange(0, len(discounts))]

    if try_product_discount:
        discount_product = DiscountProduct(
            discount=discount, product=basket.basket_items.first().product
        ).save()
        discount.refresh_from_db()
    else:
        new_product = ProductFactory.create()
        discount_product = DiscountProduct(
            discount=discount, product=new_product
        ).save()
        discount.refresh_from_db()

    resp = user_drf_client.post(
        reverse("checkout_api-redeem_discount"), {"discount": discount.discount_code}
    )

    resp_json = resp.json()

    if try_product_discount:
        assert "message" in resp_json
        assert resp_json["message"] == "Discount applied"
    else:
        assert "not found" in resp_json


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


@pytest.mark.parametrize(
    "time, expects", [["valid", True], ["past", False], ["future", False]]
)
def test_redeem_time_limited_discount(
    user, user_drf_client, products, discounts, time, expects
):
    """
    Bootstraps a basket (see create_basket) and then attempts to redeem a
    discount on it. The result will depend on whether or not the discount is
    valid for the current time.
    """
    basket = create_basket(user, products)

    assert basket is not None
    assert len(basket.basket_items.all()) > 0

    discount = discounts[random.randrange(0, len(discounts))]

    check_delta = timedelta(days=30)

    if time == "valid":
        discount.activation_date = datetime.now(pytz.timezone(TIME_ZONE)) - check_delta
        discount.expiration_date = datetime.now(pytz.timezone(TIME_ZONE)) + check_delta
    elif time == "past":
        discount.activation_date = (
            datetime.now(pytz.timezone(TIME_ZONE)) - check_delta - check_delta
        )
        discount.expiration_date = datetime.now(pytz.timezone(TIME_ZONE)) - check_delta
    elif time == "future":
        discount.activation_date = datetime.now(pytz.timezone(TIME_ZONE)) + check_delta
        discount.expiration_date = (
            datetime.now(pytz.timezone(TIME_ZONE)) + check_delta + check_delta
        )

    mocked_date_delta = timedelta(days=90)
    mocked_date_for_saving = datetime.now(pytz.timezone(TIME_ZONE)) - mocked_date_delta

    with freezegun.freeze_time(mocked_date_for_saving):
        discount.save()
        discount.refresh_from_db()

    resp = user_drf_client.post(
        reverse("checkout_api-redeem_discount"), {"discount": discount.discount_code}
    )

    resp_json = resp.json()

    if expects:
        assert "message" in resp_json
        assert resp_json["message"] == "Discount applied"
    else:
        assert "not found" in resp_json


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
    test_redeem_discount(user, user_drf_client, products, discounts, False, False)

    resp = user_drf_client.post(reverse("checkout_api-start_checkout"))

    # if there's not a payload in here, something went wrong
    assert "payload" in resp.json()

    order = Order.objects.filter(purchaser=user).get()

    assert order.state == Order.STATE.PENDING


def test_start_checkout_with_invalid_discounts(user, user_client, products, discounts):
    """
    Applies a discount, invalidates all the discounts, then hits the start
    checkout view, which should return an error.
    """
    check_delta = timedelta(days=30)
    more_check_delta = timedelta(days=120)

    test_redeem_discount(user, user_client, products, discounts, False, False)

    for discount in discounts:
        discount.activation_date = (
            datetime.now(pytz.timezone(TIME_ZONE)) - check_delta - check_delta
        )
        discount.expiration_date = datetime.now(pytz.timezone(TIME_ZONE)) - check_delta

        with freezegun.freeze_time(
            datetime.now(pytz.timezone(TIME_ZONE)) - more_check_delta
        ):
            discount.save()
            discount.refresh_from_db()

    resp = user_client.get(reverse("checkout_interstitial_page"))

    assert resp.status_code == 302


@pytest.mark.parametrize(
    "decision, expected_redirect_url, expected_state, basket_exists",
    [
        ("CANCEL", reverse("cart"), Order.STATE.CANCELED, True),
        ("DECLINE", reverse("cart"), Order.STATE.DECLINED, True),
        ("ERROR", reverse("cart"), Order.STATE.ERRORED, True),
        ("REVIEW", reverse("cart"), Order.STATE.CANCELED, True),
        ("ACCEPT", reverse("user-dashboard"), Order.STATE.FULFILLED, False),
    ],
)
def test_checkout_result(
    settings,
    user,
    user_client,
    api_client,
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
    settings.OPENEDX_SERVICE_WORKER_API_TOKEN = "mock_api_token"
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
        "transaction_id": "12345",
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

    resp = api_client.post(reverse("checkout_result_api"), payload)

    # checkout_result_api will always respond with a 200 unless validate_processor_response returns false
    assert resp.status_code == 200

    order.refresh_from_db()

    if decision == "ACCEPT":
        # test if course run is recorded in PaidCourseRun for review order
        course_run = order.purchased_runs[0]
        paid_courserun_count = PaidCourseRun.objects.filter(
            order=order, course_run=course_run, user=order.purchaser
        ).count()
        assert paid_courserun_count == 1

    else:
        assert order.state == expected_state

        # there should be no record in PaidCourseRun if order is in other states
        course_run = order.purchased_runs[0]
        paid_courserun_count = PaidCourseRun.objects.filter(
            order=order, course_run=course_run, user=order.purchaser
        ).count()
        assert paid_courserun_count == 0

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
        api_payload = {"course_run_id": course_run.courseware_id}
    else:
        api_payload = {"product_id": product.id}

    resp = user_client.get(reverse("checkout-product"), api_payload)
    assert resp.status_code == 302
    assert resp.url == reverse("cart")

    basket = Basket.objects.get(user=user)

    assert [item.product for item in basket.basket_items.all()] == [product]


@pytest.mark.parametrize(
    "cart_exists, cart_empty, expected_status, expected_message",
    [
        (False, True, status.HTTP_406_NOT_ACCEPTABLE, "No basket"),
        (True, True, status.HTTP_406_NOT_ACCEPTABLE, "No product in basket"),
        (True, False, status.HTTP_200_OK, ""),
    ],
)
def test_checkout_product_cart(
    user, user_drf_client, cart_exists, cart_empty, expected_status, expected_message
):
    """
    Verifies that cart/ works the way it is expected and generates proper responses/data in the cart page
    """
    basket = None

    if cart_exists:
        basket = BasketFactory.create(user=user)

    if not cart_empty:
        BasketItemFactory.create(basket=basket)

    resp = user_drf_client.get(reverse("checkout_api-cart"))
    assert resp.status_code == expected_status

    if cart_empty:
        assert resp.data == expected_message
    else:
        assert_drf_json_equal(resp.json(), BasketWithProductSerializer(basket).data)


def test_checkout_product_with_program_id(user, user_client):
    """
    Verifies that /cart/add?program_id=? url adds the program to the cart
    and redirect to checkout
    """
    BasketFactory.create(user=user)
    program_run = ProgramRunFactory.create()
    product = ProductFactory.create()

    program_run.products.add(product)
    api_payload = {"program_id": program_run.program.id}

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

    # 100% discount will redirect to user dashboard
    assert resp.status_code == 200 or resp.status_code == 302

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


def test_paid_and_unpaid_courserun_checkout(
    settings, user, user_client, user_drf_client, products
):
    """
    Tests checking out a paid or unpaid course run:
     - If a course run is already paid, it should redirect to cart with 302 status code including a user message in the response cookies
     - Otherwise, it should be successful with 200 status code
    """
    settings.OPENEDX_SERVICE_WORKER_API_TOKEN = "mock_api_token"
    product = products[0]
    basket = create_basket_with_product(user, product)
    order = PendingOrder.create_from_basket(basket)
    order.fulfill({"result": "Payment succeeded", "transaction_id": "12345"})
    order.save()

    basket.delete()

    # recreate basket with the same product and then call checkout/to_payment
    basket = create_basket_with_product(user, product)
    resp = user_client.get(reverse("checkout_interstitial_page"))
    assert resp.status_code == 302
    assert resp.url == reverse("cart")
    assert USER_MSG_COOKIE_NAME in resp.cookies
    assert resp.cookies[USER_MSG_COOKIE_NAME].value == encode_json_cookie_value(
        {"type": USER_MSG_TYPE_ENROLL_DUPLICATED}
    )

    basket.delete()

    unpaid_product = products[1]
    # create basket with different unpaid product
    basket = create_basket_with_product(user, unpaid_product)
    resp = user_client.get(reverse("checkout_interstitial_page"))
    assert resp.status_code == 200


@pytest.mark.parametrize(
    "decision, expected_state, basket_exists",
    [
        ("CANCEL", Order.STATE.CANCELED, True),
        ("DECLINE", Order.STATE.DECLINED, True),
        ("ERROR", Order.STATE.ERRORED, True),
        ("REVIEW", Order.STATE.CANCELED, True),
        ("ACCEPT", Order.STATE.FULFILLED, False),
    ],
)
def test_checkout_api_result(
    settings,
    user,
    user_client,
    api_client,
    mocker,
    products,
    decision,
    expected_state,
    basket_exists,
):
    """
    Tests the proper handling of an order after receiving a valid Cybersource payment response.
    """
    settings.OPENEDX_SERVICE_WORKER_API_TOKEN = "mock_api_token"
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
        "transaction_id": "12345",
    }

    # Load the pending order from the DB(factory) - should match the ref# in
    # the payload we get back

    order = Order.objects.get(state=Order.STATE.PENDING, purchaser=user)

    assert order.reference_number == payload["req_reference_number"]

    # This is kind of cheating - CyberSource will send back a payload that is
    # signed, but here we're just passing the payload as we got it back from
    # the start checkout call.

    resp = api_client.post(reverse("checkout_result_api"), payload)

    # checkout_result_api will always respond with a 200 unless validate_processor_response returns false
    assert resp.status_code == 200

    order.refresh_from_db()

    if decision == "ACCEPT":
        # test if course run is recorded in PaidCourseRun for review order
        course_run = order.purchased_runs[0]
        paid_courserun_count = PaidCourseRun.objects.filter(
            order=order, course_run=course_run, user=order.purchaser
        ).count()
        assert paid_courserun_count == 1

    else:
        assert order.state == expected_state

        # there should be no record in PaidCourseRun if order is in other states
        course_run = order.purchased_runs[0]
        paid_courserun_count = PaidCourseRun.objects.filter(
            order=order, course_run=course_run, user=order.purchaser
        ).count()
        assert paid_courserun_count == 0

    assert Basket.objects.filter(id=basket.id).exists() is basket_exists


def test_checkout_api_result_verification_failure(
    user_client,
    api_client,
    mocker,
    user,
    products,
):
    """
    Tests the failure of verifying of messages from expected from Cybersource.
    """
    mocker.patch(
        "mitol.payment_gateway.api.PaymentGateway.validate_processor_response",
        return_value=False,
    )

    create_basket(user, products)
    resp = user_client.post(reverse("checkout_api-start_checkout"))

    payload = resp.json()["payload"]
    payload = {
        **{f"req_{key}": value for key, value in payload.items()},
        "decision": Order.STATE.PENDING,
        "message": "payment processor message",
        "transaction_id": "12345",
    }

    resp = api_client.post(reverse("checkout_result_api"), payload)

    # checkout_result_api will always respond with a 403 if validate_processor_response returns False
    assert resp.status_code == 403


@pytest.mark.parametrize(
    "upgrade_deadline, status_code",
    [
        (now_in_utc() - timedelta(days=1), 302),
        (now_in_utc() + timedelta(days=1), 200),
        (None, 200),
    ],
)
def test_non_upgradable_courserun_checkout(
    user, user_client, user_drf_client, products, upgrade_deadline, status_code
):
    """
    Tests that checking out with upgradable and non-upgradable course transitions the checkout with right state
    """
    product = products[0]
    product.purchasable_object = CourseRunFactory.create(
        upgrade_deadline=upgrade_deadline
    )
    product.save()

    create_basket_with_product(user, product)

    resp = user_client.get(reverse("checkout_interstitial_page"))
    assert resp.status_code == status_code

    # In case of 302, the the user
    if status_code == 302:
        assert resp.url == reverse("cart")
        assert USER_MSG_COOKIE_NAME in resp.cookies
        assert resp.cookies[USER_MSG_COOKIE_NAME].value == encode_json_cookie_value(
            {"type": USER_MSG_TYPE_COURSE_NON_UPGRADABLE}
        )


def test_start_checkout_with_zero_value(settings, user, user_client, products):
    """
    Check that the checkout redirects the user to dashboard when basket price is zero
    """
    settings.OPENEDX_SERVICE_WORKER_API_TOKEN = "mock_api_token"
    discount = DiscountFactory.create(
        discount_type=DISCOUNT_TYPE_PERCENT_OFF, amount=100
    )
    test_redeem_discount(user, user_client, products, [discount], False, False)

    resp = user_client.get(reverse("checkout_interstitial_page"))

    assert resp.status_code == 302
    assert resp.url == reverse("user-dashboard")
    assert USER_MSG_COOKIE_NAME in resp.cookies
    order = Order.objects.filter(purchaser=user).get()
    assert resp.cookies[USER_MSG_COOKIE_NAME].value == encode_json_cookie_value(
        {
            "type": USER_MSG_TYPE_PAYMENT_ACCEPTED_NOVALUE,
            "run": order.lines.first().purchased_object.course.title,
        }
    )


def test_bulk_discount_create(admin_drf_client):
    """
    Try to make some bulk discounts.
    """

    resp = admin_drf_client.post(
        reverse("discounts_api-create_batch"),
        {
            "discount_type": DISCOUNT_TYPE_PERCENT_OFF,
            "payment_type": PAYMENT_TYPE_CUSTOMER_SUPPORT,
            "count": 5,
            "amount": 50,
            "prefix": "Generated-Code-",
            "expires": "2030-01-01T00:00:00",
            "one_time": True,
        },
    )

    assert resp.status_code == 201

    discounts = Discount.objects.filter(
        discount_code__startswith="Generated-Code-"
    ).all()

    assert len(discounts) == 5

    assert discounts[0].discount_type == DISCOUNT_TYPE_PERCENT_OFF
    assert discounts[0].amount == 50
    assert discounts[0].is_bulk
