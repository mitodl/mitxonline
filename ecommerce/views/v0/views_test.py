"""View tests for the v0 API."""

import operator as op
import random
from datetime import datetime, timedelta
from decimal import Decimal

import freezegun
import pytest
import pytz
import reversion
from django.forms.models import model_to_dict
from django.urls import reverse
from mitol.common.utils.datetime import now_in_utc
from reversion.models import Version

from b2b.constants import CONTRACT_MEMBERSHIP_CODE, CONTRACT_MEMBERSHIP_MANAGED
from b2b.factories import ContractPageFactory
from courses.factories import (
    BlockedCountryFactory,
    CourseRunEnrollmentFactory,
    CourseRunFactory,
)
from ecommerce.api import fulfill_completed_order
from ecommerce.constants import (
    DISCOUNT_TYPE_PERCENT_OFF,
    PAYMENT_TYPE_CUSTOMER_SUPPORT,
    PAYMENT_TYPE_FINANCIAL_ASSISTANCE,
    REDEMPTION_TYPE_ONE_TIME,
    ZERO_PAYMENT_DATA,
)
from ecommerce.discounts import DiscountType
from ecommerce.factories import (
    BasketFactory,
    BasketItemFactory,
    DiscountFactory,
    LineFactory,
    OrderFactory,
    ProductFactory,
    TransactionFactory,
    UnlimitedUseDiscountFactory,
)
from ecommerce.models import (
    Basket,
    BasketDiscount,
    BasketItem,
    Discount,
    DiscountProduct,
    DiscountRedemption,
    Order,
    OrderStatus,
    UserDiscount,
)
from ecommerce.serializers import (
    BasketItemSerializer,
    BasketWithProductSerializer,
    DiscountSerializer,
    ProductSerializer,
)
from flexiblepricing.constants import FlexiblePriceStatus
from flexiblepricing.factories import FlexiblePriceFactory, FlexiblePriceTierFactory
from main.constants import (
    USER_MSG_TYPE_B2B_ERROR_MISSING_ENROLLMENT_CODE,
    USER_MSG_TYPE_BASKET_EMPTY,
    USER_MSG_TYPE_COURSE_NON_UPGRADABLE,
    USER_MSG_TYPE_DISCOUNT_INVALID,
    USER_MSG_TYPE_ENROLL_BLOCKED,
    USER_MSG_TYPE_ENROLL_DUPLICATED,
)
from main.settings import TIME_ZONE
from main.test_utils import assert_drf_json_equal

pytestmark = pytest.mark.django_db


@pytest.fixture
def products():
    """Generate a batch of 5 products."""
    with reversion.create_revision():
        return ProductFactory.create_batch(5)


@pytest.fixture
def discounts():
    """Generate a batch of 5 discounts."""
    return DiscountFactory.create_batch(5)


def create_basket(user, products):
    """
    Bootstraps a basket with a product in it for testing the discount
    redemption APIs
    TODO: this should probably just be a factory
    """
    basket = Basket(user=user)
    basket.save()

    basket_item = BasketItem(
        product=products[random.randrange(0, len(products))],  # noqa: S311
        basket=basket,
        quantity=1,
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


@pytest.mark.skip_nplusone_check
def test_list_products(user_drf_client, products):
    """Test the list products API."""
    resp = user_drf_client.get(
        reverse("v0:products_api-list"),
        {
            "limit": 10,
        },
    )
    resp_products = sorted(resp.json()["results"], key=op.itemgetter("id"))

    assert len(resp_products) == len(products)

    for product, resp_product in zip(products, resp_products):
        assert_drf_json_equal(resp_product, ProductSerializer(product).data)


def test_get_products(user_drf_client, products):
    """Test the get products API."""
    product = products[random.randrange(0, len(products))]  # noqa: S311

    resp = user_drf_client.get(
        reverse("v0:products_api-detail", kwargs={"pk": product.id})
    )

    assert_drf_json_equal(resp.json(), ProductSerializer(product).data)


def test_get_products_inactive(user_drf_client, products):
    """Test that Product detail API doesn't return data for inactive product"""
    product = products[random.randrange(0, len(products))]  # noqa: S311
    product.is_active = False
    product.save()

    resp = user_drf_client.get(
        reverse("v0:products_api-detail", kwargs={"pk": product.id})
    )

    assert_drf_json_equal(
        resp.json(), {"detail": "No Product matches the given query."}
    )


def test_product_user_flexible_price(user_drf_client, user, products):
    """Test the user_flexible_price action returns product with flexible pricing info."""
    product = products[random.randrange(0, len(products))]  # noqa: S311
    course = product.purchasable_object.course

    # Create a flexible price tier and approved flexible price for the user
    tier = FlexiblePriceTierFactory.create(
        courseware_object=course,
        income_threshold_usd=25000,
        current=True,
        discount__amount=50,
        discount__discount_type=DISCOUNT_TYPE_PERCENT_OFF,
        discount__payment_type=PAYMENT_TYPE_FINANCIAL_ASSISTANCE,
    )
    FlexiblePriceFactory.create(
        income_usd=20000,
        country_of_income="US",
        user=user,
        courseware_object=course,
        status=FlexiblePriceStatus.APPROVED,
        tier=tier,
    )

    resp = user_drf_client.get(
        reverse("v0:products_api-user-flexible-price", kwargs={"pk": product.id})
    )

    assert resp.status_code == 200
    resp_data = resp.json()

    # Verify basic product fields are present
    assert resp_data["id"] == product.id
    assert resp_data["price"] == str(product.price)
    assert resp_data["description"] == product.description
    assert resp_data["is_active"] == product.is_active

    # Verify flexible price information is present
    assert "product_flexible_price" in resp_data
    assert resp_data["product_flexible_price"] is not None
    assert float(resp_data["product_flexible_price"]["amount"]) == float(
        tier.discount.amount
    )
    assert (
        resp_data["product_flexible_price"]["discount_type"]
        == DISCOUNT_TYPE_PERCENT_OFF
    )


def test_product_user_flexible_price_no_flexible_price(user_drf_client, user, products):
    """Test the user_flexible_price action when user has no flexible price."""
    product = products[random.randrange(0, len(products))]  # noqa: S311

    resp = user_drf_client.get(
        reverse("v0:products_api-user-flexible-price", kwargs={"pk": product.id})
    )

    assert resp.status_code == 200
    resp_data = resp.json()

    # Verify basic product fields are present
    assert resp_data["id"] == product.id

    # Verify flexible price discount has no amount when user has no approved flexible price
    assert resp_data["product_flexible_price"] is None


def test_product_user_flexible_price_unauthenticated(client, products):
    """Test the user_flexible_price action requires authentication."""
    product = products[random.randrange(0, len(products))]  # noqa: S311

    resp = client.get(
        reverse("v0:products_api-user-flexible-price", kwargs={"pk": product.id})
    )

    assert resp.status_code == 200
    resp_data = resp.json()

    # Verify basic product fields are present
    assert resp_data["id"] == product.id

    # Verify flexible price discount has no amount when user has no approved flexible price
    assert resp_data["product_flexible_price"] is None


def test_get_basket(user_drf_client, user):
    """Test the view that returns a state of Basket"""
    basket = BasketFactory.create(user=user)
    BasketItemFactory.create(basket=basket)
    resp = user_drf_client.get(reverse("v0:baskets_api-detail", args=[basket.id]))
    assert_drf_json_equal(resp.json(), BasketWithProductSerializer(basket).data)


def test_get_basket_items(user_drf_client, user):
    """Test the view that returns a list of BasketItems in a Basket"""
    basket = BasketFactory.create(user=user)
    basket_item = BasketItemFactory.create(basket=basket)
    basket_item_2 = BasketItemFactory.create(basket=basket)

    # this item belongs to another basket, and should not be in the response
    BasketItemFactory.create()
    resp = user_drf_client.get(
        reverse("v0:baskets_api-items-list", args=[basket.id]), follow=True
    )
    basket_info = resp.json()
    assert len(basket_info) == 2
    assert_drf_json_equal(
        resp.json(),
        [
            BasketItemSerializer(basket_item).data,
            BasketItemSerializer(basket_item_2).data,
        ],
    )


def test_get_basket_item(user_drf_client, user):
    """Test retrieving a single item from a basket."""
    basket = BasketFactory.create(user=user)
    BasketItemFactory.create(basket=basket)
    basket_item_2 = BasketItemFactory.create(basket=basket)

    # this item belongs to another basket, and should not be in the response
    BasketItemFactory.create()
    resp = user_drf_client.get(
        reverse("v0:baskets_api-items-detail", args=[basket.id, basket_item_2.id]),
        follow=True,
    )
    assert_drf_json_equal(
        resp.json(),
        BasketItemSerializer(basket_item_2).data,
    )


def test_delete_basket_item(user_drf_client, user):
    """Test the view to delete item from the basket"""
    basket_item = BasketItemFactory.create(basket__user=user)
    basket = basket_item.basket
    assert basket.basket_items.count() == 1
    user_drf_client.delete(
        reverse("v0:baskets_api-items-detail", args=[basket.id, basket_item.id]),
        content_type="application/json",
    )
    assert BasketItem.objects.filter(basket=basket).count() == 0


def test_add_basket_item(user_drf_client, user):
    """Test the view to add a new item into the Basket"""
    new_product = ProductFactory.create()
    basket = BasketFactory.create(user=user)
    BasketItemFactory.create(basket=basket)
    assert BasketItem.objects.filter(basket__user=user).count() == 1

    resp = user_drf_client.post(
        reverse("v0:baskets_api-items-list", args=[basket.id]),
        data={
            "user": user.id,
            "product": new_product.id,
            "basket": basket.id,
        },
        follow=True,
    )

    assert resp.status_code == 201
    assert BasketItem.objects.filter(basket__user=user).count() == 2


@pytest.mark.parametrize("existing_basket", [True, False])
@pytest.mark.parametrize("add_discount", [True, False])
@pytest.mark.parametrize("bad_product", [True, False])
def test_create_basket_with_products(
    user, user_client, existing_basket, add_discount, bad_product
):
    """Test creating a basket with products."""

    products = ProductFactory.create_batch(size=2)

    basket = BasketFactory(user=user) if existing_basket else None

    url = reverse("v0:baskets_api-create_with_products")
    payload = {
        "product_ids": [
            {"product_id": -3 if bad_product else product.id, "quantity": 1}
            for product in products
        ],
    }

    if add_discount:
        discount = DiscountFactory(discount_type="fixed-price", amount=100)
        payload["discount_code"] = discount.discount_code

    response = user_client.post(
        url,
        data=payload,
        content_type="application/json",
    )

    if bad_product:
        assert response.status_code == 404
        return

    assert response.status_code == 200

    basket_id = response.data["id"]
    assert Basket.objects.get(id=basket_id).basket_items.count() == 2

    if existing_basket:
        assert basket
        assert basket_id == basket.id

    if add_discount:
        assert (
            Basket.objects.get(id=basket_id)
            .discounts.filter(redeemed_discount=discount)
            .exists()
        )


@pytest.mark.parametrize(
    ("existing_basket", "add_discount", "bad_discount"),
    [
        (True, False, False),
        (False, True, False),
        (False, False, False),
        (False, True, True),
    ],
)
def test_create_basket_with_product(
    user, user_client, existing_basket, add_discount, bad_discount
):
    """Test creating a basket with a single product, and/or a discount."""

    product = ProductFactory.create()

    basket = BasketFactory(user=user) if existing_basket else None

    url = reverse(
        "v0:baskets_api-create_from_product",
        kwargs={"product_id": product.id},
    )

    if add_discount:
        if bad_discount:
            discount = DiscountFactory(
                discount_type="fixed-price", amount=100, max_redemptions=1
            )
            order = OrderFactory.create()
            DiscountRedemption.objects.create(
                redeemed_by=order.purchaser,
                redemption_date=order.created_on,
                redeemed_discount=discount,
                redeemed_order=order,
            )
        else:
            discount = DiscountFactory(discount_type="fixed-price", amount=100)

        url = reverse(
            "v0:baskets_api-create_from_product_with_discount",
            kwargs={
                "product_id": product.id,
                "discount_code": discount.discount_code,
            },
        )

    response = user_client.post(url)

    # This returns a 201 if we created the _basket line item_.
    assert response.status_code >= 200
    assert response.status_code < 300

    basket_id = response.data["id"]
    assert Basket.objects.get(id=basket_id).basket_items.count() == 1

    if existing_basket:
        assert basket
        assert basket_id == basket.id

    if add_discount:
        if bad_discount:
            assert (
                not Basket.objects.get(id=basket_id)
                .discounts.filter(redeemed_discount=discount)
                .exists()
            )
        else:
            assert (
                Basket.objects.get(id=basket_id)
                .discounts.filter(redeemed_discount=discount)
                .exists()
            )


@pytest.mark.parametrize(
    ["try_flex_pricing_discount", "try_whitespace"],  # noqa: PT006
    [
        [True, False],  # noqa: PT007
        [False, True],  # noqa: PT007
        [True, True],  # noqa: PT007
    ],
)
def test_redeem_discount(  # noqa: PLR0913
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

    discount = discounts[random.randrange(0, len(discounts))]  # noqa: S311

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


# Discount tests


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

    resp = user_drf_client.get(reverse("v0:discounts_api-list"))
    assert resp.status_code == 403

    resp = user_drf_client.get(
        reverse("v0:discounts_api-detail", kwargs={"pk": discount.id})
    )
    assert resp.status_code == 403

    resp = user_drf_client.post(reverse("v0:discounts_api-list"), discount_payload)
    assert resp.status_code == 403

    resp = user_drf_client.patch(
        reverse("v0:discounts_api-detail", kwargs={"pk": discount.id}), discount_payload
    )
    assert resp.status_code == 403

    resp = user_drf_client.delete(
        reverse("v0:discounts_api-detail", kwargs={"pk": discount.id})
    )
    assert resp.status_code == 403

    # checking CRUD ops

    resp = admin_drf_client.get(reverse("v0:discounts_api-list"))
    data = resp.json()

    assert resp.status_code == 200
    assert len(resp.json()) >= 1
    assert data[0]["id"] == discount.id

    resp = admin_drf_client.get(
        reverse("v0:discounts_api-detail", kwargs={"pk": discount.id})
    )
    data = resp.json()

    assert resp.status_code == 200
    assert data["id"] == discount.id

    resp = admin_drf_client.post(reverse("v0:discounts_api-list"), discount_payload)
    data = resp.json()

    assert resp.status_code == 201
    assert data["discount_code"] == discount_payload["discount_code"]
    assert data["id"] is not None

    data["discount_code"] = "New Discount Code"
    discount_payload = data

    resp = admin_drf_client.patch(
        reverse("v0:discounts_api-detail", kwargs={"pk": discount_payload["id"]}),
        discount_payload,
    )
    data = resp.json()

    assert resp.status_code == 200
    assert_drf_json_equal(resp.json(), DiscountSerializer(discount_payload).data)

    resp = admin_drf_client.delete(
        reverse("v0:discounts_api-detail", kwargs={"pk": discount_payload["id"]})
    )

    assert resp.status_code == 204
    assert Discount.objects.filter(pk=discount_payload["id"]).count() == 0


@pytest.mark.skip_nplusone_check
def test_discount_redemptions_api(
    user, products, discounts, admin_drf_client, user_drf_client
):
    """
    Tests pulling redemeptions from a discount after submitting an order with
    one in it.
    """

    discount = discounts[random.randrange(0, len(discounts))]  # noqa: S311

    # permissions testing
    resp = user_drf_client.get(
        reverse("v0:discounts_api-detail", kwargs={"pk": discount.id})
    )
    assert resp.status_code == 403

    resp = user_drf_client.get(
        reverse("v0:discounts_api-redemptions-list", args=[discount.id]),
    )
    assert resp.status_code == 403

    # create basket with discount, then check for redemptions

    basket = create_basket(user, products)  # noqa: F841

    resp = user_drf_client.post(
        reverse("checkout_api-redeem_discount"), {"discount": discount.discount_code}
    )

    assert resp.status_code == 200

    resp = user_drf_client.post(reverse("checkout_api-start_checkout"))

    # 100% discount will redirect to user dashboard
    assert resp.status_code == 200 or resp.status_code == 302  # noqa: PLR1714

    resp = admin_drf_client.get(
        reverse("v0:discounts_api-redemptions-list", args=[discount.id]),
    )
    assert resp.status_code == 200

    results = resp.json()
    assert len(results) > 0


def test_user_discounts_api(user_drf_client, admin_drf_client, discounts, user):
    """
    Tests retrieving and creating user discounts via the API.
    """

    discount = discounts[random.randrange(0, len(discounts))]  # noqa: S311

    # permissions testing

    resp = user_drf_client.get(reverse("v0:discounts_api-detail", args=[discount.id]))
    assert resp.status_code == 403

    resp = user_drf_client.get(
        reverse("v0:discounts_api-assignees-list", args=[discount.id]),
    )
    assert resp.status_code == 403

    # create a user discount using the model first

    user_discount = UserDiscount(discount=discount, user=user)
    user_discount.save()

    resp = admin_drf_client.get(
        reverse("v0:discounts_api-assignees-list", args=[discount.id]),
    )
    assert resp.status_code == 200

    data = resp.json()
    assert len(data) > 0

    resp = admin_drf_client.get(
        reverse(
            "v0:discounts_api-assignees-detail", args=[discount.id, user_discount.id]
        ),
    )
    assert resp.status_code == 200

    data = resp.json()
    assert data["id"] == user_discount.id

    # try to post a user discount - that should also work
    discount = DiscountFactory.create()

    resp = admin_drf_client.post(
        reverse("v0:discounts_api-assignees-list", args=[discount.id]),
        {"discount": discount.id, "user": user.id},
    )
    assert resp.status_code >= 200 and resp.status_code < 300  # noqa: PT018

    resp = admin_drf_client.get(
        reverse("v0:discounts_api-assignees-list", args=[discount.id]),
    )
    assert resp.status_code == 200

    data = resp.json()
    assert len(data) > 0


@pytest.mark.parametrize("use_redemption_type_flags", [True, False])
def test_bulk_discount_create(admin_drf_client, use_redemption_type_flags):
    """
    Try to make some bulk discounts.
    """
    test_payload = {
        "discount_type": DISCOUNT_TYPE_PERCENT_OFF,
        "payment_type": PAYMENT_TYPE_CUSTOMER_SUPPORT,
        "count": 5,
        "amount": 50,
        "prefix": "Generated-Code-",
        "expires": "2030-01-01T00:00:00",
        "one_time": True,
    }

    if use_redemption_type_flags:
        test_payload["one_time"] = True
    else:
        test_payload["redemption_type"] = REDEMPTION_TYPE_ONE_TIME

    resp = admin_drf_client.post(
        reverse("v0:discounts_api-create_batch"),
        test_payload,
    )

    assert resp.status_code == 201

    discounts = Discount.objects.filter(
        discount_code__startswith="Generated-Code-"
    ).all()

    assert len(discounts) == 5

    assert discounts[0].discount_type == DISCOUNT_TYPE_PERCENT_OFF
    assert discounts[0].redemption_type == REDEMPTION_TYPE_ONE_TIME
    assert discounts[0].amount == 50
    assert discounts[0].is_bulk


# Checkout tests


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

    discount = discounts[random.randrange(0, len(discounts))]  # noqa: S311

    if try_product_discount:
        discount_product = DiscountProduct(
            discount=discount, product=basket.basket_items.first().product
        ).save()
        discount.refresh_from_db()
    else:
        new_product = ProductFactory.create()
        discount_product = DiscountProduct(  # noqa: F841
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
    product = products[random.randrange(0, len(products), 1)]  # noqa: S311
    course = product.purchasable_object.course
    tier = FlexiblePriceTierFactory.create(
        courseware_object=course,
        income_threshold_usd=25000,
        current=True,
        discount__amount=50,
    )
    flexible_price = FlexiblePriceFactory.create(  # noqa: F841
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

    discount = discounts[random.randrange(0, len(discounts))]  # noqa: S311

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
    "time, expects",  # noqa: PT006
    [["valid", True], ["past", False], ["future", False]],  # noqa: PT007
)
def test_redeem_time_limited_discount(  # noqa: PLR0913
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

    discount = discounts[random.randrange(0, len(discounts))]  # noqa: S311

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


@pytest.mark.skip_nplusone_check
def test_start_checkout(user, user_drf_client, products):
    """
    Hits the start checkout view, which should create an Order record
    and its associated line items.
    """
    create_basket(user, products)

    resp = user_drf_client.get(reverse("v0:baskets_api-checkout"))

    # if there's not a payload in here, something went wrong
    assert "payload" in resp.json()

    order = Order.objects.filter(purchaser=user).get()

    assert order.state == OrderStatus.PENDING


@pytest.mark.skip_nplusone_check
def test_start_checkout_with_discounts(user, user_drf_client, products, discounts):
    """
    Applies a discount, then hits the start checkout view, which should create
    an Order record and its associated line items.
    """
    test_redeem_discount(user, user_drf_client, products, discounts, False, False)  # noqa: FBT003

    resp = user_drf_client.get(reverse("v0:baskets_api-checkout"))

    # if there's not a payload in here, something went wrong
    assert "payload" in resp.json()

    order = Order.objects.filter(purchaser=user).get()

    assert order.state == OrderStatus.PENDING


def test_start_checkout_with_no_lines(user, user_drf_client):
    """Test that checking out with an empty cart generates an error."""

    basket = BasketFactory.create(user=user)

    assert basket.basket_items.count() == 0

    resp = user_drf_client.get(reverse("v0:baskets_api-checkout"))

    assert "error" in resp.json()
    assert resp.json()["error"] == USER_MSG_TYPE_BASKET_EMPTY
    assert resp.status_code == 400


@pytest.mark.skip_nplusone_check
@pytest.mark.parametrize(
    ("in_contract", "contract_type"),
    [
        (
            True,
            CONTRACT_MEMBERSHIP_CODE,
        ),
        (
            False,
            CONTRACT_MEMBERSHIP_CODE,
        ),
        (
            False,
            CONTRACT_MEMBERSHIP_MANAGED,
        ),
    ],
)
def test_start_checkout_with_b2b_products(
    user, user_drf_client, in_contract, contract_type
):
    """Test that start_checkout works when there's B2B items in the basket."""

    contract = ContractPageFactory.create(
        integration_type=contract_type, membership_type=contract_type
    )
    courserun = CourseRunFactory.create(b2b_contract=contract)
    with reversion.create_revision():
        product = ProductFactory.create(purchasable_object=courserun)

    basket = BasketFactory.create(user=user)
    BasketItemFactory.create(basket=basket, product=product)

    if in_contract:
        user.b2b_contracts.add(contract)
        user.b2b_organizations.add(contract.organization)

    resp = user_drf_client.get(reverse("v0:baskets_api-checkout"))
    resp_body = resp.json()

    if in_contract:
        assert resp.status_code == 200
        assert not resp_body["error"]
        return

    assert "error" in resp_body
    assert resp_body["error"] == USER_MSG_TYPE_B2B_ERROR_MISSING_ENROLLMENT_CODE
    assert resp.status_code == 400


@pytest.mark.skip_nplusone_check
def test_start_checkout_with_blocked_country(user, user_drf_client):
    """Test that we get an error if the user's in a blocked country."""

    courserun = CourseRunFactory.create()
    blocked_country = BlockedCountryFactory.create(course=courserun.course)
    with reversion.create_revision():
        product = ProductFactory.create(purchasable_object=courserun)

    basket = BasketFactory.create(user=user)
    BasketItemFactory.create(basket=basket, product=product)

    user.legal_address.country = str(blocked_country.country)

    resp = user_drf_client.get(reverse("v0:baskets_api-checkout"))
    resp_body = resp.json()

    assert "error" in resp_body
    assert resp_body["error"] == USER_MSG_TYPE_ENROLL_BLOCKED
    assert resp.status_code == 400


@pytest.mark.skip_nplusone_check
def test_start_checkout_with_upgraded_course(user, user_drf_client):
    """Test that we get an error if the user already has a verified enrollment."""

    courserun = CourseRunFactory.create()
    with reversion.create_revision():
        product = ProductFactory.create(purchasable_object=courserun)

    basket = BasketFactory.create(user=user)
    BasketItemFactory.create(basket=basket, product=product)

    resp = user_drf_client.get(reverse("v0:baskets_api-checkout"))
    resp_body = resp.json()

    assert resp.status_code == 200

    order = Order.objects.filter(
        reference_number=resp_body["payload"]["reference_number"]
    ).get()
    fulfill_completed_order(order, ZERO_PAYMENT_DATA, basket=basket)

    basket = BasketFactory.create(user=user)
    BasketItemFactory.create(basket=basket, product=product)

    resp = user_drf_client.get(reverse("v0:baskets_api-checkout"))
    resp_body = resp.json()

    assert "error" in resp_body
    assert resp_body["error"] == USER_MSG_TYPE_ENROLL_DUPLICATED
    assert resp.status_code == 400


@pytest.mark.skip_nplusone_check
def test_start_checkout_with_unupgradable_course(user, user_drf_client):
    """Test that we get an error if the enrollment can't be upgraded."""

    courserun = CourseRunFactory.create(
        start_date=now_in_utc() - timedelta(days=30),
        upgrade_deadline=now_in_utc() - timedelta(days=15),
    )
    with reversion.create_revision():
        product = ProductFactory.create(purchasable_object=courserun)

    CourseRunEnrollmentFactory.create(user=user, run=courserun, enrollment_mode="audit")

    basket = BasketFactory.create(user=user)
    BasketItemFactory.create(basket=basket, product=product)

    resp = user_drf_client.get(reverse("v0:baskets_api-checkout"))
    resp_body = resp.json()

    assert "error" in resp_body
    assert resp_body["error"] == USER_MSG_TYPE_COURSE_NON_UPGRADABLE
    assert resp.status_code == 400


@pytest.mark.skip_nplusone_check
def test_start_checkout_with_bad_discount(user, user_drf_client):
    """Test that we get an error if the user has a bad discount in the basket."""

    basket = BasketFactory.create(user=user)
    BasketItemFactory.create(basket=basket)
    discount = UnlimitedUseDiscountFactory.create()

    other_product = ProductFactory.create()
    DiscountProduct.objects.create(
        discount=discount,
        product=other_product,
    )

    BasketDiscount.objects.create(
        redemption_date=now_in_utc(),
        redeemed_by=user,
        redeemed_discount=discount,
        redeemed_basket=basket,
    )

    resp = user_drf_client.get(reverse("v0:baskets_api-checkout"))
    resp_body = resp.json()

    assert "error" in resp_body
    assert resp_body["error"] == USER_MSG_TYPE_DISCOUNT_INVALID
    assert resp.status_code == 400


@pytest.mark.skip_nplusone_check
def test_order_history_list(user, user_drf_client):
    """Test that we can get a user's order history."""
    with reversion.create_revision():
        prod_1 = ProductFactory.create()
        prod_2 = ProductFactory.create()

    prod_1_version = Version.objects.get_for_object(prod_1).last()
    prod_2_version = Version.objects.get_for_object(prod_2).last()

    order_1 = OrderFactory.create(purchaser=user, state=OrderStatus.FULFILLED)
    order_1_line = LineFactory.create(order=order_1, product_version=prod_1_version)

    order_2 = OrderFactory.create(purchaser=user, state=OrderStatus.FULFILLED)
    order_2_line = LineFactory.create(order=order_2, product_version=prod_2_version)

    resp = user_drf_client.get(reverse("v0:orderhistory_api-list"))

    assert resp.status_code == 200

    returned_orders = resp.json()
    assert len(returned_orders) == 2
    for returned_order in returned_orders:
        assert returned_order["id"] in [
            order_1.id,
            order_2.id,
        ]
        for order_line in returned_order["lines"]:
            assert order_line["id"] in [
                order_1_line.id,
                order_2_line.id,
            ]


@pytest.mark.skip_nplusone_check
def test_order_history_retrieve(user, user_drf_client):
    """Test that we can get a user's order history."""
    with reversion.create_revision():
        prod_1 = ProductFactory.create()

    prod_1_version = Version.objects.get_for_object(prod_1).last()

    order_1 = OrderFactory.create(purchaser=user, state=OrderStatus.FULFILLED)
    order_1_line = LineFactory.create(order=order_1, product_version=prod_1_version)

    resp = user_drf_client.get(reverse("v0:orderhistory_api-list"), {"id": order_1.id})

    assert resp.status_code == 200

    returned_orders = resp.json()
    assert len(returned_orders) == 1
    returned_order = returned_orders[0]
    assert returned_order["id"] == order_1.id
    assert returned_order["lines"][0]["id"] == order_1_line.id


@pytest.mark.skip_nplusone_check
def test_order_receipt_retrieve(user, user_drf_client):
    """Test that we can get a receipt for a user's order."""
    with reversion.create_revision():
        prod_1 = ProductFactory.create()

    prod_1_version = Version.objects.get_for_object(prod_1).last()

    order_1 = OrderFactory.create(purchaser=user, state=OrderStatus.FULFILLED)
    order_1_line = LineFactory.create(order=order_1, product_version=prod_1_version)
    TransactionFactory.create(order=order_1)

    resp = user_drf_client.get(
        reverse("v0:order_receipt_api", kwargs={"pk": order_1.id})
    )

    assert resp.status_code == 200

    receipt = resp.json()

    assert receipt["reference_number"] == order_1.reference_number
    assert Decimal(receipt["lines"][0]["price"]) == order_1_line.total_price
    # The TransactionFactory creates a transaction with no payment data so this
    # should be None.
    assert receipt["transactions"]["card_number"] is None
