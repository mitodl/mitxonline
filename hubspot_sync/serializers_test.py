"""
Tests for hubspot_sync serializers
"""

# pylint: disable=unused-argument, redefined-outer-name

from decimal import Decimal

import pytest
from django.contrib.contenttypes.models import ContentType
from mitol.common.utils import now_in_utc
from mitol.hubspot_api.api import format_app_id
from mitol.hubspot_api.models import HubspotObject

from courses.factories import (
    CourseRunCertificateFactory,
    CourseRunEnrollmentFactory,
    CourseRunFactory,
    ProgramCertificateFactory,
)
from ecommerce.constants import (
    DISCOUNT_TYPE_DOLLARS_OFF,
    DISCOUNT_TYPE_FIXED_PRICE,
    DISCOUNT_TYPE_PERCENT_OFF,
)
from ecommerce.factories import (
    DiscountFactory,
    DiscountRedemptionFactory,
    ProductFactory,
)
from ecommerce.models import Order, Product
from hubspot_sync.serializers import (
    ORDER_STATUS_MAPPING,
    HubspotContactSerializer,
    LineSerializer,
    OrderToDealSerializer,
    ProductSerializer,
    format_product_name,
)

pytestmark = [pytest.mark.django_db]


@pytest.mark.parametrize(
    "text_id, expected",  # noqa: PT006
    [
        ["course-v1:MITxOnline+SysEngxNAV+R1", "Run 1"],  # noqa: PT007
        ["course-v1:MITxOnline+SysEngxNAV+R10", "Run 10"],  # noqa: PT007
        (
            "course-v1:MITxOnline+SysEngxNAV",
            "course-v1:MITxOnline+SysEngxNAV",
        ),
    ],
)
def test_serialize_product(text_id, expected):
    """Test that ProductSerializer has correct data"""
    product = ProductFactory.create(
        purchasable_object=CourseRunFactory.create(courseware_id=text_id)
    )
    run = product.purchasable_object
    serialized_data = ProductSerializer(instance=product).data
    assert serialized_data.get("name").startswith(f"{run.title}: {expected}")
    assert serialized_data.get("price") == product.price.to_eng_string()
    assert serialized_data.get("description") == product.description
    assert serialized_data.get("unique_app_id") == format_app_id(product.id)


def test_serialize_line(hubspot_order):
    """Test that LineSerializer produces the correct serialized data"""
    line = hubspot_order.lines.first()
    product = Product.objects.get(id=line.product_version.object_id)
    course_run_enrollment = CourseRunEnrollmentFactory(
        run=product.purchasable_object, user=hubspot_order.purchaser
    )
    serialized_data = LineSerializer(instance=line).data
    assert serialized_data == {
        "hs_product_id": HubspotObject.objects.get(
            content_type=ContentType.objects.get_for_model(Product),
            object_id=product.id,
        ).hubspot_id,
        "quantity": line.quantity,
        "status": line.order.state,
        "product_id": product.purchasable_object.readable_id,
        "name": format_product_name(product),
        "price": "200.00",
        "unique_app_id": format_app_id(line.id),
        "enrollment_mode": course_run_enrollment.enrollment_mode,
        "change_status": course_run_enrollment.change_status,
    }


def test_serialize_line_no_corresponding_enrollment(hubspot_order):
    """Test that LineSerializer produces the correct serialized data when a user does not have a CourseRunEnrollment record that corresponds with the Order"""
    line = hubspot_order.lines.first()
    product = Product.objects.get(id=line.product_version.object_id)
    serialized_data = LineSerializer(instance=line).data
    assert serialized_data == {
        "hs_product_id": HubspotObject.objects.get(
            content_type=ContentType.objects.get_for_model(Product),
            object_id=product.id,
        ).hubspot_id,
        "quantity": line.quantity,
        "status": line.order.state,
        "product_id": product.purchasable_object.readable_id,
        "name": format_product_name(product),
        "price": "200.00",
        "unique_app_id": format_app_id(line.id),
        "enrollment_mode": None,
        "change_status": None,
    }


@pytest.mark.parametrize("status", [Order.STATE.FULFILLED, Order.STATE.PENDING])
def test_serialize_order(settings, hubspot_order, status):
    """Test that OrderToDealSerializer produces the correct serialized data"""
    hubspot_order.state = status
    serialized_data = OrderToDealSerializer(instance=hubspot_order).data
    assert serialized_data == {
        "dealname": f"MITXONLINE-ORDER-{hubspot_order.id}",
        "dealstage": ORDER_STATUS_MAPPING[status],
        "amount": hubspot_order.total_price_paid.to_eng_string(),
        "discount_amount": "0.00",
        "discount_type": None,
        "discount_percent": "0",
        "closedate": (
            int(hubspot_order.updated_on.timestamp() * 1000)
            if status == Order.STATE.FULFILLED
            else None
        ),
        "coupon_code": None,
        "status": hubspot_order.state,
        "pipeline": settings.HUBSPOT_PIPELINE_ID,
        "unique_app_id": format_app_id(hubspot_order.id),
    }


@pytest.mark.parametrize(
    "discount_type, amount, percent_off, amount_off",  # noqa: PT006
    [
        [DISCOUNT_TYPE_PERCENT_OFF, Decimal(75), "75.00", "150.00"],  # noqa: PT007
        [DISCOUNT_TYPE_DOLLARS_OFF, Decimal(75), "37.50", "75.00"],  # noqa: PT007
        [DISCOUNT_TYPE_FIXED_PRICE, Decimal(75), "62.50", "125.00"],  # noqa: PT007
    ],
)
def test_serialize_order_with_coupon(  # noqa: PLR0913
    settings, hubspot_order, discount_type, amount, percent_off, amount_off
):
    """Test that OrderToDealSerializer produces the correct serialized data for an order with coupon"""
    discount = DiscountFactory.create(
        amount=amount,
        discount_type=discount_type,
    )
    coupon_redemption = DiscountRedemptionFactory(
        redeemed_discount=discount,
        redeemed_order=hubspot_order,
        redeemed_by=hubspot_order.purchaser,
        redemption_date=now_in_utc(),
    )
    serialized_data = OrderToDealSerializer(instance=hubspot_order).data
    assert serialized_data == {
        "dealname": f"MITXONLINE-ORDER-{hubspot_order.id}",
        "dealstage": ORDER_STATUS_MAPPING[hubspot_order.state],
        "amount": hubspot_order.total_price_paid.to_eng_string(),
        "discount_amount": amount_off,
        "closedate": (
            int(hubspot_order.updated_on.timestamp() * 1000)
            if hubspot_order.state == Order.STATE.FULFILLED
            else None
        ),
        "coupon_code": coupon_redemption.redeemed_discount.discount_code,
        "discount_type": coupon_redemption.redeemed_discount.discount_type,
        "discount_percent": percent_off,
        "status": hubspot_order.state,
        "pipeline": settings.HUBSPOT_PIPELINE_ID,
        "unique_app_id": format_app_id(hubspot_order.id),
    }


def test_serialize_contact(settings, user, mocker):
    """Test that HubspotContactSerializer includes program and course run certificates for the user"""
    mocker.patch(
        "hubspot_sync.management.commands.configure_hubspot_properties._upsert_custom_properties",
    )
    program_cert_1 = ProgramCertificateFactory.create(user=user)
    program_cert_2 = ProgramCertificateFactory.create(user=user)
    course_run_cert_1 = CourseRunCertificateFactory.create(user=user)
    course_run_cert_2 = CourseRunCertificateFactory.create(user=user)
    serialized_data = HubspotContactSerializer(instance=user).data
    assert (
        serialized_data["program_certificates"]
        == f"{program_cert_1.program!s};{program_cert_2.program!s}"
    )
    assert (
        serialized_data["course_run_certificates"]
        == f"{course_run_cert_1.course_run!s};{course_run_cert_2.course_run!s}"
    )
