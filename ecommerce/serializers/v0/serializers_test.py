"""Tests for v0 ecommerce serializers."""

from decimal import Decimal

import pytest
import reversion
from django.test import Client, RequestFactory
from django.urls import reverse
from mitol.common.utils import now_in_utc
from reversion.models import Version

from courses.models import CourseRun, EnrollmentMode, Program
from ecommerce.api import generate_checkout_payload
from ecommerce.constants import (
    DISCOUNT_TYPE_FIXED_PRICE,
    DISCOUNT_TYPE_PAID_AMOUNT_OFF,
    REDEMPTION_TYPE_PROGRAM_CHILD_PURCHASE,
)
from ecommerce.factories import (
    BasketFactory,
    BasketItemFactory,
    DiscountFactory,
    OrderFactory,
    PaidAmountOffDiscountFactory,
    ProductFactory,
    ProgramProductFactory,
)
from ecommerce.models import (
    BasketDiscount,
    DiscountProduct,
    Line,
    Order,
    OrderStatus,
)
from ecommerce.serializers.v0 import (
    BasketWithProductSerializer,
    TransactionLineSerializer,
    V0DiscountSerializer,
)
from ecommerce.views.legacy.views_test import create_basket
from openedx.constants import EDX_ENROLLMENT_AUDIT_MODE

pytestmark = [pytest.mark.django_db]


def create_order(mocker, user, products):
    """Create a fulfilled order for the given user and products."""
    mocker.patch(
        "mitol.payment_gateway.api.PaymentGateway.validate_processor_response",
        return_value=True,
    )
    create_basket(user, products)

    rf = RequestFactory()
    request = rf.get("/")
    request.user = user
    request.session = {}
    checkout_payload = generate_checkout_payload(request)

    payload = checkout_payload["payload"]
    payload = {
        **{f"req_{key}": value for key, value in payload.items()},
        "decision": "ACCEPT",
        "message": "payment processor message",
        "transaction_id": "12345",
    }

    order = Order.objects.get(state=OrderStatus.PENDING, purchaser=user)

    client = Client()
    client.force_login(user)
    client.post(reverse("checkout-result-callback"), payload)

    order.refresh_from_db()
    return order


def build_expected_line(instance):
    """Build the expected serialized line dict for a given order line."""
    total_paid = instance.get_discounted_unit_price() * instance.quantity
    discount = instance.product.price * instance.quantity - total_paid

    content_object = instance.product.purchasable_object
    (content_title, readable_id) = (None, None)

    if isinstance(content_object, Program):
        content_title = content_object.title
        readable_id = content_object.readable_id
    elif isinstance(content_object, CourseRun):
        readable_id = content_object.course.readable_id
        content_title = f"{content_object.course_number} {content_object.title}"

    return dict(  # noqa: C408
        quantity=instance.quantity,
        total_paid=str(total_paid),
        discount=str(discount),
        CEUs=None,
        content_title=content_title,
        content_type=instance.product.content_type.model,
        readable_id=readable_id,
        price=str(instance.product.price),
        start_date=content_object.start_date,
        end_date=content_object.end_date,
        has_free_audit=content_object.has_free_audit,
    )


@pytest.mark.skip_nplusone_check
def test_courserun_order_lines_serializer(settings, mocker, user):
    """Test TransactionLineSerializer for course run products."""
    settings.OPENEDX_SERVICE_WORKER_API_TOKEN = "mock_api_token"  # noqa: S105

    with reversion.create_revision():
        products = ProductFactory.create_batch(5)

    order = create_order(mocker, user, products)

    expected_lines = [build_expected_line(line) for line in order.lines.all()]
    serialized_data = TransactionLineSerializer(instance=order.lines, many=True).data

    assert serialized_data == expected_lines


@pytest.mark.skip_nplusone_check
def test_program_order_lines_serializer(settings, mocker, user):
    """Test TransactionLineSerializer for program products."""
    settings.OPENEDX_SERVICE_WORKER_API_TOKEN = "mock_api_token"  # noqa: S105

    with reversion.create_revision():
        products = ProgramProductFactory.create_batch(5)

    order = create_order(mocker, user, products)

    expected_lines = [build_expected_line(line) for line in order.lines.all()]
    serialized_data = TransactionLineSerializer(instance=order.lines, many=True).data

    assert serialized_data == expected_lines


@pytest.mark.skip_nplusone_check
def test_order_lines_serializer_tolerates_deleted_courseware_object(
    settings, mocker, user
):
    """
    A receipt must still serialize when its product's courseware object is gone.

    `purchasable_object` is a GenericForeignKey with no database constraint, so
    deleting the course run leaves the product pointing at nothing.
    """
    settings.OPENEDX_SERVICE_WORKER_API_TOKEN = "mock_api_token"  # noqa: S105

    with reversion.create_revision():
        products = ProductFactory.create_batch(1)

    order = create_order(mocker, user, products)
    CourseRun.objects.filter(id=products[0].object_id).delete()

    serialized_data = TransactionLineSerializer(instance=order.lines, many=True).data

    assert serialized_data[0]["start_date"] is None
    assert serialized_data[0]["end_date"] is None
    assert serialized_data[0]["content_title"] is None


def _fulfilled_line(price, *, quantity=1, discounted_unit_price=None):
    """
    A fulfilled order carrying one line, priced independently of any discount row.

    Re-fetched so the serializer sees the column's numeric(20,5) read-back
    rather than the value handed to create(). discounted_unit_price defaults to
    the undiscounted price.
    """
    with reversion.create_revision():
        product = ProductFactory.create(price=price)
    order = OrderFactory.create(state=OrderStatus.FULFILLED)
    line = Line.objects.create(
        order=order,
        purchased_object_id=product.object_id,
        purchased_content_type_id=product.content_type_id,
        product_version=Version.objects.get_for_object(product).first(),
        quantity=quantity,
        discounted_unit_price=(
            price if discounted_unit_price is None else discounted_unit_price
        ),
    )
    return Line.objects.get(pk=line.pk)


def test_receipt_line_reports_the_recorded_price():
    """The receipt reports the recorded price; discount is the line total off list."""
    line = _fulfilled_line(
        Decimal("300.00"), quantity=2, discounted_unit_price=Decimal("200.00")
    )

    data = TransactionLineSerializer(instance=line).data

    assert data["price"] == "300.00"
    assert data["discount"] == "200.00"
    assert data["total_paid"] == "400.00"


def test_receipt_line_shows_no_discount_when_the_price_was_not_discounted():
    """A line recorded at list price reports full price and a zero discount."""
    line = _fulfilled_line(Decimal("300.00"))

    data = TransactionLineSerializer(instance=line).data

    assert data["discount"] == "0.00"
    assert data["total_paid"] == "300.00"


@pytest.mark.skip_nplusone_check
def test_order_line_reports_a_free_audit_track(settings, mocker, user):
    """A run with an audit mode tells the receipt the learner can fall back to it."""
    settings.OPENEDX_SERVICE_WORKER_API_TOKEN = "mock_api_token"  # noqa: S105

    with reversion.create_revision():
        products = ProductFactory.create_batch(1)
    order = create_order(mocker, user, products)
    run = CourseRun.objects.get(id=products[0].object_id)
    run.enrollment_modes.add(
        EnrollmentMode.objects.get_or_create(mode_slug=EDX_ENROLLMENT_AUDIT_MODE)[0]
    )

    serialized = TransactionLineSerializer(instance=order.lines, many=True).data

    assert serialized[0]["has_free_audit"] is True


@pytest.mark.skip_nplusone_check
def test_order_line_reports_no_free_audit_track(settings, mocker, user):
    """Without an audit mode, refunding costs the learner access entirely."""
    settings.OPENEDX_SERVICE_WORKER_API_TOKEN = "mock_api_token"  # noqa: S105

    with reversion.create_revision():
        products = ProductFactory.create_batch(1)
    order = create_order(mocker, user, products)
    CourseRun.objects.get(id=products[0].object_id).enrollment_modes.clear()

    serialized = TransactionLineSerializer(instance=order.lines, many=True).data

    assert serialized[0]["has_free_audit"] is False


def test_v0_discount_serializer_rejects_a_malformed_paid_amount_off_discount():
    """
    The API mirror of Discount.check_program_child_purchase_validity returns a 400,
    not a 500. The individual shape clauses are pinned in models_test.
    """
    data = {
        "amount": "0",
        "automatic": True,
        "discount_type": "paid-amount-off",
        "redemption_type": "unlimited",
        "discount_code": "linked-serializer-test",
    }
    serializer = V0DiscountSerializer(data=data)

    assert not serializer.is_valid()
    assert "program-child-purchase redemption type" in str(serializer.errors)


def test_v0_discount_serializer_accepts_a_well_formed_paid_amount_off_discount():
    """Without this, a validate() that rejected every paid-amount-off discount would pass."""
    serializer = V0DiscountSerializer(
        data={
            "amount": "0",
            "automatic": True,
            "discount_type": DISCOUNT_TYPE_PAID_AMOUNT_OFF,
            "redemption_type": REDEMPTION_TYPE_PROGRAM_CHILD_PURCHASE,
            "discount_code": "linked-serializer-test",
        }
    )

    assert serializer.is_valid(), serializer.errors


def test_v0_discount_serializer_rejects_a_patch_that_sets_an_amount():
    """
    The rules read through to the stored row, so a PATCH carrying only the
    amount is still judged as a paid-amount-off discount.
    """
    discount = PaidAmountOffDiscountFactory.create()

    serializer = V0DiscountSerializer(
        instance=discount, data={"amount": "10"}, partial=True
    )

    assert not serializer.is_valid()
    assert "store 0" in str(serializer.errors)


def test_v0_discount_serializer_rejects_converting_a_discount_with_a_courserun_product():
    """
    The program-products clause has to fail validation rather than save(): a
    Django ValidationError out of save() is not converted, so it 500s and leaves
    the row un-PATCHable.
    """
    discount = DiscountFactory.create(automatic=False)
    DiscountProduct.objects.create(discount=discount, product=ProductFactory.create())

    serializer = V0DiscountSerializer(
        instance=discount,
        data={
            "discount_type": DISCOUNT_TYPE_PAID_AMOUNT_OFF,
            "redemption_type": REDEMPTION_TYPE_PROGRAM_CHILD_PURCHASE,
            "amount": "0",
            "automatic": True,
        },
        partial=True,
    )

    assert not serializer.is_valid()
    assert "program products" in str(serializer.errors)


def test_basket_serializer_hides_a_paid_amount_off_discount(user):
    """
    A paid-amount-off discount's stored amount is always 0 and its real
    per-user value is resolved elsewhere (hq#11846), so there is nothing to
    render for it yet.
    """
    basket = BasketFactory.create(user=user)
    BasketItemFactory.create(basket=basket)
    BasketDiscount.objects.create(
        redemption_date=now_in_utc(),
        redeemed_by=user,
        redeemed_discount=PaidAmountOffDiscountFactory.create(),
        redeemed_basket=basket,
    )

    data = BasketWithProductSerializer(instance=basket).data

    assert data["discounts"] == []


def test_basket_serializer_shows_a_fixed_price_discount_equal_to_the_product_price(
    user,
):
    """
    A B2B contract sets a run's price with a fixed-price discount, which can
    land on the list price itself; the shopper still needs the code confirmed
    as applied.
    """
    basket = BasketFactory.create(user=user)
    basket_item = BasketItemFactory.create(basket=basket)
    BasketDiscount.objects.create(
        redemption_date=now_in_utc(),
        redeemed_by=user,
        redeemed_discount=DiscountFactory.create(
            amount=basket_item.product.price, discount_type=DISCOUNT_TYPE_FIXED_PRICE
        ),
        redeemed_basket=basket,
    )

    data = BasketWithProductSerializer(instance=basket).data

    assert len(data["discounts"]) == 1


def test_basket_serializer_shows_a_discount_on_a_zero_price_product(user):
    """B2B products are often $0 yet require a code, which must confirm as applied."""
    basket = BasketFactory.create(user=user)
    BasketItemFactory.create(basket=basket, product=ProductFactory.create(price=0))
    BasketDiscount.objects.create(
        redemption_date=now_in_utc(),
        redeemed_by=user,
        redeemed_discount=DiscountFactory.create(),
        redeemed_basket=basket,
    )

    data = BasketWithProductSerializer(instance=basket).data

    assert len(data["discounts"]) == 1
