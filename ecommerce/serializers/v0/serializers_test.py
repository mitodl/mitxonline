"""Tests for v0 ecommerce serializers."""

from decimal import Decimal

import pytest
import reversion
from django.test import Client, RequestFactory
from django.urls import reverse

from courses.models import CourseRun, Program
from ecommerce.api import generate_checkout_payload
from ecommerce.factories import ProductFactory, ProgramProductFactory
from ecommerce.models import Order, OrderStatus
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
    coupon_redemption = instance.order.discounts.first()
    discount = 0.0

    if coupon_redemption:
        discount = instance.product.price - instance.discounted_price

    total_paid = (instance.product.price - Decimal(discount)) * instance.quantity

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
