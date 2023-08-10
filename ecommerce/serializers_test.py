import json
from decimal import Decimal

import pytest
import reversion
from dateutil.parser import parse
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory
from django.urls import reverse
from mitol.common.utils import now_in_utc

from courses.factories import CourseRunFactory, ProgramFactory, ProgramRunFactory
from courses.models import CourseRun, ProgramRun
from ecommerce.constants import (
    CYBERSOURCE_CARD_TYPES,
    DISCOUNT_TYPE_DOLLARS_OFF,
    DISCOUNT_TYPE_FIXED_PRICE,
    DISCOUNT_TYPE_PERCENT_OFF,
)
from ecommerce.discounts import DiscountType
from ecommerce.factories import (
    BasketItemFactory,
    ProductFactory,
    UnlimitedUseDiscountFactory,
)
from ecommerce.models import BasketDiscount, Order
from ecommerce.serializers import (
    BaseProductSerializer,
    BasketItemSerializer,
    BasketSerializer,
    BasketWithProductSerializer,
    CourseRunProductPurchasableObjectSerializer,
    OrderReceiptSerializer,
    ProductFlexibilePriceSerializer,
    ProductSerializer,
    ProgramRunProductPurchasableObjectSerializer,
    TransactionLineSerializer,
    TransactionOrderSerializer,
    TransactionPurchaserSerializer,
    TransactionPurchaseSerializer,
)
from ecommerce.views_test import create_basket, payment_gateway_settings
from flexiblepricing.constants import FlexiblePriceStatus
from flexiblepricing.factories import FlexiblePriceFactory
from flexiblepricing.models import FlexiblePrice
from main.test_utils import assert_drf_json_equal
from users.factories import UserFactory

pytestmark = [pytest.mark.django_db]


@pytest.fixture()
def products():
    with reversion.create_revision():
        return ProductFactory.create_batch(5)


def test_product_course_serializer(mock_context):
    """
    Tests serialization of a product that has an associated course.
    """
    program = ProgramFactory.create()
    run = CourseRunFactory.create()
    program.add_requirement(run.course)
    product = ProductFactory.create(purchasable_object=run)
    product_serialized = ProductSerializer(instance=product).data
    run_serialized = CourseRunProductPurchasableObjectSerializer(instance=run).data

    assert_drf_json_equal(
        product_serialized,
        {
            "description": product.description,
            "id": product.id,
            "is_active": product.is_active,
            "price": str(product.price),
            "purchasable_object": run_serialized,
        },
    )

    product_serialized = BaseProductSerializer(instance=product).data
    assert_drf_json_equal(
        product_serialized,
        {
            "description": product.description,
            "id": product.id,
            "is_active": product.is_active,
            "price": str(product.price),
        },
    )


def test_product_program_serializer(mock_context):
    """
    Tests serialization of a product that has an associated program.
    """
    run = ProgramRunFactory.create()
    product = ProductFactory.create(purchasable_object=run)
    product_serialized = ProductSerializer(instance=product).data
    run_serialized = ProgramRunProductPurchasableObjectSerializer(instance=run).data

    assert_drf_json_equal(
        product_serialized,
        {
            "description": product.description,
            "id": product.id,
            "is_active": product.is_active,
            "price": str(product.price),
            "purchasable_object": run_serialized,
        },
    )


def test_product_flexible_price_serializer(mock_context):
    """
    Tests serialization of a product that has an associated flexible price for the user.
    """
    program = ProgramFactory.create()
    run = CourseRunFactory.create()
    program.add_requirement(run.course)
    product = ProductFactory.create(purchasable_object=run)
    flexible_price = FlexiblePriceFactory.create(
        courseware_object=run.course,
        user=mock_context["request"].user,
        status=FlexiblePriceStatus.APPROVED,
    )
    product_serialized = ProductFlexibilePriceSerializer(
        context={**mock_context}, instance=product
    ).data
    product_serialized["product_flexible_price"]["amount"] = float(
        product_serialized["product_flexible_price"]["amount"]
    )
    assert_drf_json_equal(
        product_serialized,
        {
            "description": product.description,
            "id": product.id,
            "is_active": product.is_active,
            "price": str(product.price),
            "product_flexible_price": {
                "amount": float(flexible_price.tier.discount.amount),
                "automatic": flexible_price.tier.discount.automatic,
                "discount_code": flexible_price.tier.discount.discount_code,
                "discount_type": flexible_price.tier.discount.discount_type,
                "payment_type": flexible_price.tier.discount.payment_type,
                "id": flexible_price.tier.discount.id,
                "max_redemptions": flexible_price.tier.discount.max_redemptions,
                "redemption_type": flexible_price.tier.discount.redemption_type,
                "activation_date": flexible_price.tier.discount.activation_date,
                "expiration_date": flexible_price.tier.discount.expiration_date,
                "is_redeemed": flexible_price.tier.discount.is_redeemed,
            },
        },
    )


def test_basket_serializer(mock_context):
    """
    Tests serialization of a Basket with products for a user.
    """
    basket_item = BasketItemFactory.create()
    basket = basket_item.basket
    basket_serialized = BasketSerializer(instance=basket).data
    basket_item_serialized = BasketItemSerializer(basket_item).data

    assert_drf_json_equal(
        basket_serialized,
        {
            "user": basket.user.id,
            "id": basket.id,
            "basket_items": [basket_item_serialized],
        },
    )


def test_basket_item_serializer(mock_context):
    """
    Tests serialization of a BasketItem with products for a user.
    """
    basket_item = BasketItemFactory.create()
    basket_item_serialized = BasketItemSerializer(basket_item).data

    assert_drf_json_equal(
        basket_item_serialized,
        {
            "basket": basket_item.basket.id,
            "id": basket_item.id,
            "product": basket_item.product.id,
        },
    )


def test_basket_with_product_serializer():
    """
    Tests serialization of a basket with the attached products (and any
    discounts applied).
    """

    basket_item = BasketItemFactory.create()
    discount = UnlimitedUseDiscountFactory.create()
    user = UserFactory.create()

    basket_discount = BasketDiscount(
        redeemed_by=user,
        redeemed_discount=discount,
        redeemed_basket=basket_item.basket,
        redemption_date=now_in_utc(),
    )
    basket_discount.save()

    serialized_basket = BasketWithProductSerializer(basket_item.basket).data

    logic = DiscountType.for_discount(discount)
    discount_price = logic.get_discounted_price([discount], basket_item.product)

    assert serialized_basket["total_price"] == basket_item.product.price
    assert serialized_basket["discounted_price"] == discount_price
    assert len(serialized_basket["discounts"]) == 1


@pytest.mark.parametrize(
    "discount_amount, discount_type",
    [
        (0, DISCOUNT_TYPE_PERCENT_OFF),
        (50, DISCOUNT_TYPE_PERCENT_OFF),
        (0, DISCOUNT_TYPE_DOLLARS_OFF),
        (50, DISCOUNT_TYPE_DOLLARS_OFF),
        (0, DISCOUNT_TYPE_FIXED_PRICE),
        (50, DISCOUNT_TYPE_FIXED_PRICE),
    ],
)
def test_basket_product_serializer_with_zero_value_discount(
    discount_amount, discount_type
):
    """
    Tests serialization of a basket with the attached products and different discount values and types.
    """
    basket_item = BasketItemFactory.create()
    discount = UnlimitedUseDiscountFactory.create(
        amount=discount_amount, discount_type=discount_type
    )
    user = UserFactory.create()

    basket_discount = BasketDiscount(
        redeemed_by=user,
        redeemed_discount=discount,
        redeemed_basket=basket_item.basket,
        redemption_date=now_in_utc(),
    )
    basket_discount.save()

    serialized_basket = BasketWithProductSerializer(basket_item.basket).data

    logic = DiscountType.for_discount(discount)
    discount_price = logic.get_discounted_price([discount], basket_item.product)

    assert serialized_basket["total_price"] == basket_item.product.price

    if discount_amount == 0 and discount_type in [
        DISCOUNT_TYPE_DOLLARS_OFF,
        DISCOUNT_TYPE_PERCENT_OFF,
    ]:
        assert serialized_basket["discounted_price"] == basket_item.product.price
        assert len(serialized_basket["discounts"]) == 0
    else:
        assert serialized_basket["discounted_price"] == discount_price
        assert len(serialized_basket["discounts"]) == 1


def create_order_receipt(mocker, user, products, user_client):
    """
    Sets up an order for use with the receipt serializer tests.
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
        "decision": "ACCEPT",
        "message": "payment processor message",
        "transaction_id": "12345",
    }

    order = Order.objects.get(state=Order.STATE.PENDING, purchaser=user)

    resp = user_client.post(reverse("checkout-result-callback"), payload)

    order.refresh_from_db()
    return order


def get_test_order_data(order, receipt_data):
    return {
        "coupon": None,
        "lines": [],
        "order": {
            "id": order.id,
            "created_on": order.created_on,
            "reference_number": order.reference_number,
        },
        "purchaser": {
            "first_name": order.purchaser.legal_address.first_name,
            "last_name": order.purchaser.legal_address.last_name,
            "email": order.purchaser.email,
            "country": order.purchaser.legal_address.country,
            "state_or_territory": "",
            "city": "",
            "postal_code": "",
            "company": "",
            "street_address_1": None,
            "street_address_2": None,
            "street_address_3": None,
            "street_address_4": None,
            "street_address_5": None,
            "street_address": [],
        },
        "receipt": {
            "card_number": receipt_data["req_card_number"]
            if "req_card_number" in receipt_data
            else None,
            "card_type": CYBERSOURCE_CARD_TYPES[receipt_data["req_card_type"]]
            if "req_card_type" in receipt_data
            else None,
            "payment_method": receipt_data["req_payment_method"]
            if "req_payment_method" in receipt_data
            else None,
            "bill_to_email": receipt_data["req_bill_to_email"]
            if "req_bill_to_email" in receipt_data
            else None,
            "name": f"{receipt_data['req_bill_to_forename']} {receipt_data['req_bill_to_surname']}"
            if "req_bill_to_forename" in receipt_data
            or "req_bill_to_surname" in receipt_data
            else None,
        },
    }


def get_receipt_serializer_test_data(mocker, user, products, user_client):
    order = create_order_receipt(mocker, user, products, user_client)
    receipt_data = order.transactions.order_by("-created_on").first().data
    test_data = get_test_order_data(order, receipt_data)

    return (order, test_data)


def test_order_receipt_purchase_serializer(
    settings, mocker, user, products, user_client
):
    settings.OPENEDX_SERVICE_WORKER_API_TOKEN = "mock_api_token"
    (order, test_data) = get_receipt_serializer_test_data(
        mocker, user, products, user_client
    )

    serialized_data = TransactionPurchaseSerializer(instance=order).data

    assert serialized_data == test_data["receipt"]


def test_order_receipt_purchaser_serializer(
    settings, mocker, user, products, user_client
):
    settings.OPENEDX_SERVICE_WORKER_API_TOKEN = "mock_api_token"
    (order, test_data) = get_receipt_serializer_test_data(
        mocker, user, products, user_client
    )

    serialized_data = TransactionPurchaserSerializer(instance=order).data

    assert serialized_data == test_data["purchaser"]


def test_order_receipt_order_serializer(settings, mocker, user, products, user_client):
    settings.OPENEDX_SERVICE_WORKER_API_TOKEN = "mock_api_token"
    (order, test_data) = get_receipt_serializer_test_data(
        mocker, user, products, user_client
    )

    serialized_data = TransactionOrderSerializer(instance=order).data
    serialized_data["created_on"] = parse(serialized_data["created_on"])

    assert serialized_data == test_data["order"]


def test_order_receipt_lines_serializer(settings, mocker, user, products, user_client):
    settings.OPENEDX_SERVICE_WORKER_API_TOKEN = "mock_api_token"
    (order, test_data) = get_receipt_serializer_test_data(
        mocker, user, products, user_client
    )

    for instance in order.lines.all():
        coupon_redemption = instance.order.discounts.first()
        discount = 0.0

        if coupon_redemption:
            discount = instance.product.price - instance.discounted_price

        total_paid = (instance.product.price - Decimal(discount)) * instance.quantity

        content_object = instance.product.purchasable_object
        (content_title, readable_id) = (None, None)

        if isinstance(content_object, ProgramRun):
            content_title = content_object.program.title
            readable_id = content_object.program.readable_id
        elif isinstance(content_object, CourseRun):
            readable_id = content_object.course.readable_id
            content_title = "{} {}".format(
                content_object.course_number, content_object.title
            )

        line = dict(
            quantity=instance.quantity,
            total_paid=str(total_paid),
            discount=str(discount),
            CEUs=None,
            content_title=content_title,
            readable_id=readable_id,
            price=str(instance.product.price),
            start_date=content_object.start_date,
            end_date=content_object.end_date,
        )
        test_data["lines"].append(line)

    serialized_data = TransactionLineSerializer(instance=order.lines, many=True).data

    assert serialized_data == test_data["lines"]
