"""Tests for v0 ecommerce serializers."""

from decimal import Decimal

import pytest
import reversion
from django.test import Client, RequestFactory
from django.urls import reverse
from reversion.models import Version

from courses.models import CourseRun, Program
from ecommerce.api import generate_checkout_payload
from ecommerce.factories import OrderFactory, ProductFactory, ProgramProductFactory
from ecommerce.models import Line, Order, OrderStatus
from ecommerce.serializers.v0 import TransactionLineSerializer
from ecommerce.views.legacy.views_test import create_basket

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
    rather than the value handed to create().
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
        discounted_unit_price=discounted_unit_price,
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


def test_receipt_line_shows_no_discount_when_none_was_recorded():
    """A line with no recorded price reports full price and a zero discount."""
    line = _fulfilled_line(Decimal("300.00"))

    data = TransactionLineSerializer(instance=line).data

    assert data["discount"] == "0.00"
    assert data["total_paid"] == "300.00"
