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
from ecommerce.models import OrderStatus, Product
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


@pytest.mark.parametrize("status", [OrderStatus.FULFILLED, OrderStatus.PENDING])
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
            if status == OrderStatus.FULFILLED
            else None
        ),
        "coupon_code": None,
        "status": hubspot_order.state,
        "pipeline": settings.HUBSPOT_PIPELINE_ID,
        "unique_app_id": format_app_id(hubspot_order.id),
    }


@pytest.mark.parametrize(
    "discount_type, amount, percent_off, amount_off, zero_value_product",  # noqa: PT006
    [
        [DISCOUNT_TYPE_PERCENT_OFF, Decimal(75), "75.00", "150.00", False],  # noqa: PT007
        [DISCOUNT_TYPE_DOLLARS_OFF, Decimal(75), "37.50", "75.00", False],  # noqa: PT007
        [DISCOUNT_TYPE_FIXED_PRICE, Decimal(75), "62.50", "125.00", False],  # noqa: PT007
        [DISCOUNT_TYPE_FIXED_PRICE, Decimal(0), "100.00", "200.00", False],  # noqa: PT007
        [DISCOUNT_TYPE_FIXED_PRICE, Decimal(0), "100.00", "0.00", True],  # noqa: PT007
    ],
)
def test_serialize_order_with_coupon(  # noqa: PLR0913
    settings,
    hubspot_order,
    hubspot_b2b_order,
    discount_type,
    amount,
    percent_off,
    amount_off,
    zero_value_product,
):
    """Test that OrderToDealSerializer produces the correct serialized data for an order with coupon"""

    # This uses a zero-value order - B2B products are often $0, and require a discount code.
    if zero_value_product:
        hubspot_order = hubspot_b2b_order

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
            if hubspot_order.state == OrderStatus.FULFILLED
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

def test_serialize_contact_removes_semicolons_from_program_names(settings, user, mocker):
    """Test that HubspotContactSerializer removes semicolons from program certificate names"""
    mocker.patch(
        "hubspot_sync.management.commands.configure_hubspot_properties._upsert_custom_properties",
    )
    # Create a program certificate where the program's string representation contains a semicolon
    program_cert = ProgramCertificateFactory.create(user=user)
    
    # Mock the program's __str__ method to return a value with semicolons
    mocker.patch.object(
        program_cert.program, '__str__', return_value="Test Program; With Semicolon"
    )
    
    serialized_data = HubspotContactSerializer(instance=user).data
    
    # Verify that semicolons are removed from the program name
    assert serialized_data["program_certificates"] == "Test Program With Semicolon"
    # Ensure no semicolons remain in the final string
    assert ";" not in serialized_data["program_certificates"].replace(";", "")


def test_serialize_contact_removes_semicolons_from_course_run_names(settings, user, mocker):
    """Test that HubspotContactSerializer removes semicolons from course run certificate names"""
    mocker.patch(
        "hubspot_sync.management.commands.configure_hubspot_properties._upsert_custom_properties",
    )
    # Create a course run certificate where the course run's string representation contains a semicolon
    course_run_cert = CourseRunCertificateFactory.create(user=user)
    
    # Mock the course run's __str__ method to return a value with semicolons
    mocker.patch.object(
        course_run_cert.course_run, '__str__', return_value="Test Course; Run With Semicolon"
    )
    
    serialized_data = HubspotContactSerializer(instance=user).data
    
    # Verify that semicolons are removed from the course run name
    assert serialized_data["course_run_certificates"] == "Test Course Run With Semicolon"
    # Ensure no semicolons remain in the final string except for joining
    assert ";" not in serialized_data["course_run_certificates"].replace(";", "")


def test_serialize_contact_multiple_certificates_with_semicolons(settings, user, mocker):
    """Test that HubspotContactSerializer properly handles multiple certificates with semicolons"""
    mocker.patch(
        "hubspot_sync.management.commands.configure_hubspot_properties._upsert_custom_properties",
    )
    
    # Create multiple certificates
    program_cert_1 = ProgramCertificateFactory.create(user=user)
    program_cert_2 = ProgramCertificateFactory.create(user=user)
    course_run_cert_1 = CourseRunCertificateFactory.create(user=user)
    course_run_cert_2 = CourseRunCertificateFactory.create(user=user)
    
    # Mock the string representations to include semicolons
    mocker.patch.object(
        program_cert_1.program, '__str__', return_value="Program; One"
    )
    mocker.patch.object(
        program_cert_2.program, '__str__', return_value="Program; Two"
    )
    mocker.patch.object(
        course_run_cert_1.course_run, '__str__', return_value="Course; Run One"
    )
    mocker.patch.object(
        course_run_cert_2.course_run, '__str__', return_value="Course; Run Two"
    )
    
    serialized_data = HubspotContactSerializer(instance=user).data
    
    # Verify that semicolons are removed from individual names but preserved as separators
    assert serialized_data["program_certificates"] == "Program One;Program Two"
    assert serialized_data["course_run_certificates"] == "Course Run One;Course Run Two"
    
    # Count semicolons to ensure only separator semicolons remain
    program_semicolons = serialized_data["program_certificates"].count(";")
    course_run_semicolons = serialized_data["course_run_certificates"].count(";")
    
    # Should have exactly 1 separator semicolon (2 items = 1 separator)
    assert program_semicolons == 1
    assert course_run_semicolons == 1
