"""Tests for hubspot_sync.api"""

import json

import pytest
import reversion
from django.contrib.contenttypes.models import ContentType
from hubspot.crm.objects import ApiException
from mitol.common.utils.datetime import now_in_utc
from mitol.hubspot_api.factories import HubspotObjectFactory, SimplePublicObjectFactory
from mitol.hubspot_api.models import HubspotObject
from reversion.models import Version

from courses.constants import ALL_ENROLL_CHANGE_STATUSES
from courses.factories import (
    CourseRunCertificateFactory,
    CourseRunEnrollmentFactory,
    ProgramCertificateFactory,
)
from ecommerce.factories import LineFactory, OrderFactory, ProductFactory
from ecommerce.models import Product
from hubspot_sync import api
from hubspot_sync.api import get_hubspot_id_for_object
from hubspot_sync.conftest import FAKE_HUBSPOT_ID
from hubspot_sync.serializers import (
    LineSerializer,
    OrderToDealSerializer,
    ProductSerializer,
)
from openedx.constants import EDX_ENROLLMENT_AUDIT_MODE, EDX_ENROLLMENT_VERIFIED_MODE
from users.factories import UserFactory

pytestmark = [pytest.mark.django_db]


@pytest.mark.django_db
def test_make_contact_sync_message(user, mocker):
    """Test make_contact_sync_message serializes a user and returns a properly formatted sync message"""
    mocker.patch(
        "hubspot_sync.management.commands.configure_hubspot_properties._upsert_custom_properties",
    )
    course_certificate_1 = CourseRunCertificateFactory.create(user=user)
    course_certificate_2 = CourseRunCertificateFactory.create(user=user)
    program_certificate_1 = ProgramCertificateFactory.create(user=user)
    program_certificate_2 = ProgramCertificateFactory.create(user=user)
    contact_sync_message = api.make_contact_sync_message_from_user(user)
    assert contact_sync_message.properties == {
        "country": user.legal_address.country,
        "state": user.legal_address.state or "",
        "email": user.email,
        "firstname": user.legal_address.first_name,
        "lastname": user.legal_address.last_name,
        "name": user.name,
        "yearofbirth": user.user_profile.year_of_birth,
        "gender": user.user_profile.gender,
        "company": user.user_profile.company,
        "companysize": user.user_profile.company_size or "",
        "jobtitle": user.user_profile.job_title,
        "industry": user.user_profile.industry,
        "jobfunction": user.user_profile.job_function,
        "yearsexperience": user.user_profile.years_experience or "",
        "leadershiplevel": user.user_profile.leadership_level,
        "highesteducation": user.user_profile.highest_education,
        "typeisstudent": user.user_profile.type_is_student,
        "typeisprofessional": user.user_profile.type_is_professional,
        "typeiseducator": user.user_profile.type_is_educator,
        "typeisother": user.user_profile.type_is_other,
        "program_certificates": str(program_certificate_1.program)
        + ";"
        + str(program_certificate_2.program),
        "course_run_certificates": str(course_certificate_1.course_run)
        + ";"
        + str(course_certificate_2.course_run),
    }


@pytest.mark.django_db
def test_make_deal_sync_message(hubspot_order):
    """Test make_deal_sync_message serializes an order and returns a properly formatted sync message"""
    deal_sync_message = api.make_deal_sync_message_from_order(hubspot_order)
    serialized_order = OrderToDealSerializer(hubspot_order).data

    assert deal_sync_message.properties == {
        "dealname": serialized_order["dealname"],
        "amount": serialized_order["amount"],
        "status": serialized_order["status"],
        "dealstage": serialized_order["dealstage"],
        "closedate": serialized_order["closedate"] or "",
        "coupon_code": serialized_order["coupon_code"] or "",
        "discount_type": serialized_order["discount_type"] or "",
        "discount_percent": serialized_order["discount_percent"] or "",
        "discount_amount": serialized_order["discount_amount"] or "",
        "pipeline": serialized_order["pipeline"],
        "unique_app_id": serialized_order["unique_app_id"],
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "enrollment_mode", [EDX_ENROLLMENT_AUDIT_MODE, EDX_ENROLLMENT_VERIFIED_MODE]
)
@pytest.mark.parametrize("change_status", ALL_ENROLL_CHANGE_STATUSES)
def test_make_line_item_sync_message(
    mocker, hubspot_order, enrollment_mode, change_status
):
    """Test make_line_item_sync_message serializes an order line and returns a properly formatted sync message"""
    line = hubspot_order.lines.first()
    course_run_enrollment = CourseRunEnrollmentFactory.create(
        user=line.order.purchaser,
        enrollment_mode=enrollment_mode,
        change_status=change_status,
        run=line.purchased_object,
    )
    serialized_line = LineSerializer(line).data
    line_item_sync_message = api.make_line_item_sync_message_from_line(line)

    assert line_item_sync_message.properties == {
        "name": serialized_line["name"],
        "hs_product_id": serialized_line["hs_product_id"],
        "status": serialized_line["status"],
        "product_id": serialized_line["product_id"],
        "price": serialized_line["price"],
        "quantity": serialized_line["quantity"],
        "unique_app_id": serialized_line["unique_app_id"],
        "enrollment_mode": serialized_line["enrollment_mode"],
        "change_status": serialized_line["change_status"],
    }
    assert serialized_line["enrollment_mode"] == course_run_enrollment.enrollment_mode
    assert serialized_line["change_status"] == course_run_enrollment.change_status


@pytest.mark.django_db
def test_make_product_sync_message():
    """Test make_product_sync_message serializes a product and returns a properly formatted sync message"""
    product = ProductFactory()
    serialized_product = ProductSerializer(product).data
    product_sync_message = api.make_product_sync_message_from_product(product)

    assert product_sync_message.properties == {
        "name": serialized_product["name"],
        "price": serialized_product["price"],
        "description": serialized_product["description"],
        "unique_app_id": serialized_product["unique_app_id"],
    }


def test_sync_contact_with_hubspot(mock_hubspot_api):
    """Test that the hubspot CRM API is called properly for a contact sync"""
    user = UserFactory.create()
    api.sync_contact_with_hubspot(user)
    assert (
        api.HubspotObject.objects.get(
            object_id=user.id, content_type__model="user"
        ).hubspot_id
        == FAKE_HUBSPOT_ID
    )
    mock_hubspot_api.return_value.crm.objects.basic_api.create.assert_called_once_with(
        simple_public_object_input=api.make_contact_sync_message_from_user(user),
        object_type=api.HubspotObjectType.CONTACTS.value,
    )
    user.refresh_from_db()
    assert user.hubspot_sync_datetime is not None


def test_sync_contact_with_hubspot_error(mocker, mock_hubspot_api):
    """Test that the user's hubspot_sync_datetime is not populated if the call to HubSpot throws an exception"""
    user = UserFactory.create()
    mock_create = mock_hubspot_api.return_value.crm.objects.basic_api.create
    mock_create.side_effect = ApiException(
        http_resp=mocker.Mock(
            data=json.dumps(
                {
                    "message": "something bad happened",
                }
            ),
            reason="",
            status=400,
        )
    )
    with pytest.raises(ApiException) as exc:  # noqa: F841
        api.sync_contact_with_hubspot(user)
    user.refresh_from_db()
    assert user.hubspot_sync_datetime is None


def test_existing_user_sync_contact_with_hubspot_error(mocker, mock_hubspot_api):
    """Test that the user's hubspot_sync_datetime is not populated if the call to HubSpot throws an exception"""
    # Fake successful first call to HubSpot
    current_datetime = now_in_utc()
    user = UserFactory.create(hubspot_sync_datetime=current_datetime)

    # Failed second call to HubSpot
    mock_create = mock_hubspot_api.return_value.crm.objects.basic_api.create
    mock_create.side_effect = ApiException(
        http_resp=mocker.Mock(
            data=json.dumps(
                {
                    "message": "something bad happened",
                }
            ),
            reason="",
            status=400,
        )
    )
    with pytest.raises(ApiException) as exc:  # noqa: F841
        api.sync_contact_with_hubspot(user)
    user.refresh_from_db()
    assert user.hubspot_sync_datetime == current_datetime


def test_sync_product_with_hubspot(mock_hubspot_api):
    """Test that the hubspot CRM API is called properly for a product sync"""
    product = ProductFactory.create()
    api.sync_product_with_hubspot(product)
    assert (
        api.HubspotObject.objects.get(
            object_id=product.id, content_type__model="product"
        ).hubspot_id
        == FAKE_HUBSPOT_ID
    )
    mock_hubspot_api.return_value.crm.objects.basic_api.create.assert_called_once_with(
        simple_public_object_input=api.make_product_sync_message_from_product(product),
        object_type=api.HubspotObjectType.PRODUCTS.value,
    )


def test_sync_deal_with_hubspot(mocker, mock_hubspot_api, hubspot_order):
    """Test that the hubspot CRM API is called properly for a deal sync"""
    mock_sync_line = mocker.patch(
        "hubspot_sync.api.sync_line_item_with_hubspot", autospec=True
    )
    api.sync_deal_with_hubspot(hubspot_order)

    mock_hubspot_api.return_value.crm.objects.basic_api.create.assert_called_once_with(
        simple_public_object_input=api.make_deal_sync_message_from_order(hubspot_order),
        object_type=api.HubspotObjectType.DEALS.value,
    )

    mock_sync_line.assert_any_call(hubspot_order.lines.first())

    assert (
        api.HubspotObject.objects.get(
            object_id=hubspot_order.id, content_type__model="order"
        ).hubspot_id
        == FAKE_HUBSPOT_ID
    )


def test_sync_line_item_with_hubspot(
    mocker, mock_hubspot_api, hubspot_order, hubspot_order_id
):
    """Test that the hubspot CRM API is called properly for a line_item sync"""
    line = hubspot_order.lines.first()
    course_run_enrollment = CourseRunEnrollmentFactory.create(user=line.order.purchaser)  # noqa: F841
    api.sync_line_item_with_hubspot(line)
    assert (
        api.HubspotObject.objects.get(
            object_id=line.id, content_type__model="line"
        ).hubspot_id
        == FAKE_HUBSPOT_ID
    )
    mock_hubspot_api.return_value.crm.objects.associations_api.create.assert_called_once_with(
        api.HubspotObjectType.LINES.value,
        FAKE_HUBSPOT_ID,
        api.HubspotObjectType.DEALS.value,
        hubspot_order_id,
        api.HubspotAssociationType.LINE_DEAL.value,
    )


@pytest.mark.parametrize("match_all", [True, False])
def test_sync_contact_hubspot_ids_to_hubspot(mocker, mock_hubspot_api, match_all):
    """sync_contact_hubspot_ids_to_hubspot should create HubspotObjects and return True if all users matched"""
    matches = 3 if match_all else 2
    users = UserFactory.create_batch(3)
    contacts = [
        SimplePublicObjectFactory(properties={"email": user.email.capitalize()})
        for user in users[0:matches]
    ]
    mock_hubspot_api.return_value.crm.objects.basic_api.get_page.side_effect = [
        mocker.Mock(results=contacts, paging=None)
    ]
    assert api.sync_contact_hubspot_ids_to_db() is match_all
    assert HubspotObject.objects.filter(content_type__model="user").count() == matches


@pytest.mark.parametrize("multiple_emails", [True, False])
def test_sync_contact_hubspot_ids_alternate(mocker, mock_hubspot_api, multiple_emails):
    """sync_contact_hubspot_ids_to_hubspot should be able to match by alternate emails"""
    user = UserFactory.create()
    additional_emails = (
        f"{user.email.capitalize()};other_email@fake.edu"
        if multiple_emails
        else user.email
    )
    contacts = [
        SimplePublicObjectFactory(
            properties={
                "hs_additional_emails": additional_emails,
                "email": "fake@fake.edu",
            }
        )
    ]
    mock_hubspot_api.return_value.crm.objects.basic_api.get_page.side_effect = [
        mocker.Mock(results=contacts, paging=None)
    ]
    assert api.sync_contact_hubspot_ids_to_db() is True
    assert HubspotObject.objects.filter(content_type__model="user").count() == 1


@pytest.mark.parametrize("match_all", [True, False])
def test_sync_product_hubspot_ids_to_hubspot(mocker, mock_hubspot_api, match_all):
    """sync_product_hubspot_ids_to_db should create HubspotObjects and return True if all products matched"""
    matches = 3 if match_all else 2
    db_products = ProductFactory.create_batch(3)
    hs_products = [
        SimplePublicObjectFactory(properties={"name": api.format_product_name(product)})
        for product in db_products[0:matches]
    ]
    mock_hubspot_api.return_value.crm.objects.basic_api.get_page.side_effect = [
        mocker.Mock(results=hs_products, paging=None)
    ]
    assert api.sync_product_hubspot_ids_to_db() is match_all
    assert (
        HubspotObject.objects.filter(content_type__model="product").count() == matches
    )


def test_sync_product_hubspot_ids_dupe_names(mocker, mock_hubspot_api):
    """sync_product_hubspot_ids_to_db should handle dupe product names"""
    mocker.patch(
        "hubspot_sync.api.format_product_name", return_value="Same Name Product"
    )
    db_products = ProductFactory.create_batch(2)
    hs_products = [
        SimplePublicObjectFactory(
            properties={"name": "Same Name Product", "price": product.price}
        )
        for product in db_products
    ]
    mock_hubspot_api.return_value.crm.objects.basic_api.get_page.side_effect = [
        mocker.Mock(results=hs_products, paging=None)
    ]
    assert api.sync_product_hubspot_ids_to_db() is True
    assert HubspotObject.objects.filter(content_type__model="product").count() == 2


@pytest.mark.parametrize("match_all_lines", [True, False])
@pytest.mark.parametrize("match_all_deals", [True, False])
def test_sync_deal_hubspot_ids_to_hubspot(
    mocker, mock_hubspot_api, match_all_deals, match_all_lines
):
    """sync_deal_hubspot_ids_to_hubspot should create HubspotObjects and return True if all deals & lines matched"""
    deal_matches = 3 if match_all_deals else 2
    line_matches = 3 if match_all_lines else 2
    lines = []
    for _ in range(3):
        order = OrderFactory.create()
        with reversion.create_revision():
            product = ProductFactory.create()
        version = Version.objects.get_for_object(product).first()
        lines.append(
            LineFactory.create(order=order, product_version=version, quantity=1)
        )
    deals = [
        SimplePublicObjectFactory(
            properties={
                "dealname": f"MITXONLINE-ORDER-{line.order.id}",
                "amount": str(line.order.total_price_paid),
            }
        )
        for line in lines[0:deal_matches]
    ]
    # This deal should be ignored
    SimplePublicObjectFactory(
        properties={
            "dealname": "MITXONLINE-ORDER-MANUAL",
            "amount": "400.00",
        }
    )
    hs_products = [
        HubspotObjectFactory.create(
            content_object=Product.objects.get(pk=line.product_version.object_id),
            content_type=ContentType.objects.get_for_model(Product),
            object_id=Product.objects.get(pk=line.product_version.object_id).id,
        )
        for line in lines
    ]
    line_items = [
        SimplePublicObjectFactory(
            properties={"hs_product_id": hsp.hubspot_id, "quantity": 1}
        )
        for hsp in hs_products[0:line_matches]
    ]
    mock_hubspot_api.return_value.crm.objects.basic_api.get_page.side_effect = [
        mocker.Mock(results=deals, paging=None),  # deals
    ]
    mock_hubspot_api.return_value.crm.deals.associations_api.get_all.side_effect = [
        *[mocker.Mock(results=[SimplePublicObjectFactory()]) for _ in line_items],
        mocker.Mock(results=[]),
    ]  # associations
    mock_hubspot_api.return_value.crm.line_items.basic_api.get_by_id.side_effect = [
        SimplePublicObjectFactory(properties={"hs_product_id": hsp.hubspot_id})
        for hsp in hs_products[0:line_matches]
    ]  # line_item details
    assert api.sync_deal_hubspot_ids_to_db() is (match_all_lines and match_all_deals)
    assert (
        HubspotObject.objects.filter(content_type__model="order").count()
        == deal_matches
    )
    assert HubspotObject.objects.filter(content_type__model="line").count() == min(
        deal_matches, line_matches
    )


@pytest.mark.parametrize("match_lines,quantity", [[True, 2], [False, 3]])  # noqa: PT006, PT007
def test_sync_deal_line_hubspot_ids_to_hubspot_two_lines(
    mocker, mock_hubspot_api, match_lines, quantity
):
    """Matches should be made correctly for an order with 2 lines"""
    order = OrderFactory.create()
    with reversion.create_revision():
        product = ProductFactory.create()
    version = Version.objects.get_for_object(product).first()
    hs_order = HubspotObjectFactory.create(
        content_object=order,
        content_type=ContentType.objects.get_for_model(order),
        object_id=order.id,
    )
    hs_product = HubspotObjectFactory.create(
        content_object=product,
        content_type=ContentType.objects.get_for_model(Product),
        object_id=product.id,
    )
    lines = (  # noqa: F841
        LineFactory.create(order=order, product_version=version, quantity=1),
        LineFactory.create(order=order, product_version=version, quantity=quantity),
    )
    lines_response = [
        SimplePublicObjectFactory(
            properties={"hs_product_id": hs_product.hubspot_id, "quantity": 1},
        ),
        SimplePublicObjectFactory(
            properties={"hs_product_id": hs_product.hubspot_id, "quantity": 2},
        ),
    ]
    mocker.patch(
        "hubspot_sync.api.get_line_items_for_deal", return_value=lines_response
    )
    assert (
        api.sync_deal_line_hubspot_ids_to_db(order, hs_order.hubspot_id) is match_lines
    )


@pytest.mark.parametrize("error", [True, False])
def test_get_hubspot_id_for_user(mocker, user, error):
    """get_hubspot_id_for_user should call find_contact and create HubspotObject"""
    hs_user = SimplePublicObjectFactory() if not error else ValueError
    mocker.patch("hubspot_sync.api.find_contact", side_effect=[hs_user])
    mock_log = mocker.patch("hubspot_sync.api.log.exception")
    get_hubspot_id_for_object(user)
    if error:
        mock_log.assert_called_once()
    else:
        assert HubspotObject.objects.filter(hubspot_id=hs_user.id).exists()


def test_get_hubspot_id_raises(mocker, user):
    """get_hubspot_id should handle errors appropriately"""
    mocker.patch("hubspot_sync.api.find_contact", side_effect=[ValueError])
    mock_log = mocker.patch("hubspot_sync.api.log.exception")
    with pytest.raises(ValueError) as exc:  # noqa: PT011
        get_hubspot_id_for_object(user, raise_error=True)
    mock_log.assert_called_once()
    assert f"Hubspot id could not be found for user for id {user.id}" == str(exc.value)
