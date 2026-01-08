"""Generate Hubspot message bodies for various model objects"""

import logging
import re
import sys
from decimal import Decimal
from typing import List  # noqa: UP035

from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from hubspot.crm.objects import (
    SimplePublicObject,
    SimplePublicObjectInput,
)
from mitol.common.utils.datetime import now_in_utc
from mitol.hubspot_api.api import (
    HubspotAssociationType,
    HubspotObjectType,
    associate_objects_request,
    find_contact,
    find_deal,
    find_line_item,
    find_product,
    format_app_id,
    get_all_objects,
    get_line_items_for_deal,
    make_object_properties_message,
    sync_object_property,
    sync_property_group,
    transform_object_properties,
    upsert_object_request,
)
from mitol.hubspot_api.models import HubspotObject

from courses.constants import ALL_ENROLL_CHANGE_STATUSES
from courses.models import CourseRun, Program
from ecommerce import models
from ecommerce.constants import (
    DISCOUNT_TYPE_DOLLARS_OFF,
    DISCOUNT_TYPE_FIXED_PRICE,
    DISCOUNT_TYPE_PERCENT_OFF,
)
from ecommerce.models import Line, Order, Product
from hubspot_sync.rate_limiter import wait_for_hubspot_rate_limit
from openedx.constants import EDX_ENROLLMENT_AUDIT_MODE, EDX_ENROLLMENT_VERIFIED_MODE
from users.models import (
    COMPANY_SIZE_CHOICES,
    GENDER_CHOICES,
    HIGHEST_EDUCATION_CHOICES,
    YRS_EXPERIENCE_CHOICES,
    User,
)

log = logging.getLogger(__name__)

CUSTOM_ECOMMERCE_PROPERTIES = {
    # defines which hubspot properties are mapped with which local properties when objects are synced.
    # See https://developers.hubspot.com/docs/methods/ecomm-bridge/ecomm-bridge-overview for more details
    "deals": {
        "groups": [{"name": "coupon", "label": "Coupon"}],
        "properties": [
            {
                "name": "status",
                "label": "Order Status",
                "description": "The current status of the order",
                "groupName": "dealinformation",
                "type": "enumeration",
                "fieldType": "select",
                "options": [
                    {
                        "value": models.OrderStatus.FULFILLED,
                        "label": models.OrderStatus.FULFILLED,
                        "displayOrder": 0,
                        "hidden": False,
                    },
                    {
                        "value": models.OrderStatus.CANCELED,
                        "label": models.OrderStatus.CANCELED,
                        "displayOrder": 1,
                        "hidden": False,
                    },
                    {
                        "value": models.OrderStatus.ERRORED,
                        "label": models.OrderStatus.ERRORED,
                        "displayOrder": 2,
                        "hidden": False,
                    },
                    {
                        "value": models.OrderStatus.DECLINED,
                        "label": models.OrderStatus.DECLINED,
                        "displayOrder": 3,
                        "hidden": False,
                    },
                    {
                        "value": models.OrderStatus.PENDING,
                        "label": models.OrderStatus.PENDING,
                        "displayOrder": 4,
                        "hidden": False,
                    },
                    {
                        "value": models.OrderStatus.REFUNDED,
                        "label": models.OrderStatus.REFUNDED,
                        "displayOrder": 5,
                        "hidden": False,
                    },
                    {
                        "value": models.OrderStatus.PARTIALLY_REFUNDED,
                        "label": models.OrderStatus.PARTIALLY_REFUNDED,
                        "displayOrder": 6,
                        "hidden": False,
                    },
                    {
                        "value": models.OrderStatus.REVIEW,
                        "label": models.OrderStatus.REVIEW,
                        "displayOrder": 7,
                        "hidden": False,
                    },
                ],
            },
            {
                "name": "discount_percent",
                "label": "Percent Discount",
                "description": "Percentage off regular price",
                "groupName": "coupon",
                "type": "number",
                "fieldType": "number",
            },
            {
                "name": "discount_amount",
                "label": "Discount savings",
                "description": "The discount on the deal as an amount.",
                "groupName": "coupon",
                "type": "number",
                "fieldType": "number",
            },
            {
                "name": "discount_type",
                "label": "Discount Type",
                "description": "Type of discount (percent-off or dollars-off or fixed-price)",
                "groupName": "coupon",
                "type": "enumeration",
                "fieldType": "select",
                "options": [
                    {
                        "value": DISCOUNT_TYPE_PERCENT_OFF,
                        "label": DISCOUNT_TYPE_PERCENT_OFF,
                        "displayOrder": 0,
                        "hidden": False,
                    },
                    {
                        "value": DISCOUNT_TYPE_DOLLARS_OFF,
                        "label": DISCOUNT_TYPE_DOLLARS_OFF,
                        "displayOrder": 1,
                        "hidden": False,
                    },
                    {
                        "value": DISCOUNT_TYPE_FIXED_PRICE,
                        "label": DISCOUNT_TYPE_FIXED_PRICE,
                        "displayOrder": 2,
                        "hidden": False,
                    },
                ],
            },
            {
                "name": "coupon_code",
                "label": "Coupon Code",
                "description": "The coupon code used for the purchase",
                "groupName": "coupon",
                "type": "string",
                "fieldType": "text",
            },
            {
                "name": "unique_app_id",
                "label": "Unique App ID",
                "description": "The unique app ID for the deal",
                "groupName": "dealinformation",
                "type": "string",
                "fieldType": "text",
                "hasUniqueValue": True,
                "hidden": True,
            },
        ],
    },
    "contacts": {
        "groups": [],
        "properties": [
            {
                "name": "name",
                "label": "Name",
                "description": "Full name",
                "groupName": "contactinformation",
                "type": "string",
                "fieldType": "text",
            },
            {
                "name": "yearofbirth",
                "label": "Year of birth",
                "description": "Year of birth",
                "groupName": "contactinformation",
                "type": "number",
                "fieldType": "number",
            },
            {
                "name": "gender",
                "label": "Gender",
                "description": "Gender",
                "groupName": "contactinformation",
                "type": "enumeration",
                "fieldType": "select",
                "options": [
                    {
                        "value": GENDER_CHOICES[0][0],
                        "label": GENDER_CHOICES[0][1],
                        "displayOrder": 0,
                        "hidden": False,
                    },
                    {
                        "value": GENDER_CHOICES[1][0],
                        "label": GENDER_CHOICES[1][1],
                        "displayOrder": 1,
                        "hidden": False,
                    },
                    {
                        "value": GENDER_CHOICES[2][0],
                        "label": GENDER_CHOICES[2][1],
                        "displayOrder": 2,
                        "hidden": False,
                    },
                    {
                        "value": GENDER_CHOICES[3][0],
                        "label": GENDER_CHOICES[3][1],
                        "displayOrder": 3,
                        "hidden": False,
                    },
                    {
                        "value": GENDER_CHOICES[4][0],
                        "label": GENDER_CHOICES[4][1],
                        "displayOrder": 4,
                        "hidden": False,
                    },
                ],
            },
            {
                "name": "companysize",
                "label": "Number of employees",
                "description": "Company size",
                "groupName": "contactinformation",
                "type": "enumeration",
                "fieldType": "select",
                "options": [
                    {
                        "value": COMPANY_SIZE_CHOICES[1][0],
                        "label": COMPANY_SIZE_CHOICES[1][1],
                        "displayOrder": 0,
                        "hidden": False,
                    },
                    {
                        "value": COMPANY_SIZE_CHOICES[2][0],
                        "label": COMPANY_SIZE_CHOICES[2][1],
                        "displayOrder": 1,
                        "hidden": False,
                    },
                    {
                        "value": COMPANY_SIZE_CHOICES[3][0],
                        "label": COMPANY_SIZE_CHOICES[3][1],
                        "displayOrder": 2,
                        "hidden": False,
                    },
                    {
                        "value": COMPANY_SIZE_CHOICES[4][0],
                        "label": COMPANY_SIZE_CHOICES[4][1],
                        "displayOrder": 3,
                        "hidden": False,
                    },
                    {
                        "value": COMPANY_SIZE_CHOICES[5][0],
                        "label": COMPANY_SIZE_CHOICES[5][1],
                        "displayOrder": 4,
                        "hidden": False,
                    },
                    {
                        "value": COMPANY_SIZE_CHOICES[6][0],
                        "label": COMPANY_SIZE_CHOICES[6][1],
                        "displayOrder": 5,
                        "hidden": False,
                    },
                    {
                        "value": COMPANY_SIZE_CHOICES[7][0],
                        "label": COMPANY_SIZE_CHOICES[7][1],
                        "displayOrder": 6,
                        "hidden": False,
                    },
                ],
            },
            {
                "name": "jobfunction",
                "label": "Job Function",
                "description": "Job Function",
                "groupName": "contactinformation",
                "type": "string",
                "fieldType": "text",
            },
            {
                "name": "yearsexperience",
                "label": "Years of experience",
                "description": "Years of experience",
                "groupName": "contactinformation",
                "type": "enumeration",
                "fieldType": "select",
                "options": [
                    {
                        "value": YRS_EXPERIENCE_CHOICES[1][0],
                        "label": YRS_EXPERIENCE_CHOICES[1][1],
                        "displayOrder": 0,
                        "hidden": False,
                    },
                    {
                        "value": YRS_EXPERIENCE_CHOICES[2][0],
                        "label": YRS_EXPERIENCE_CHOICES[2][1],
                        "displayOrder": 1,
                        "hidden": False,
                    },
                    {
                        "value": YRS_EXPERIENCE_CHOICES[3][0],
                        "label": YRS_EXPERIENCE_CHOICES[3][1],
                        "displayOrder": 2,
                        "hidden": False,
                    },
                    {
                        "value": YRS_EXPERIENCE_CHOICES[4][0],
                        "label": YRS_EXPERIENCE_CHOICES[4][1],
                        "displayOrder": 3,
                        "hidden": False,
                    },
                    {
                        "value": YRS_EXPERIENCE_CHOICES[5][0],
                        "label": YRS_EXPERIENCE_CHOICES[5][1],
                        "displayOrder": 4,
                        "hidden": False,
                    },
                    {
                        "value": YRS_EXPERIENCE_CHOICES[6][0],
                        "label": YRS_EXPERIENCE_CHOICES[6][1],
                        "displayOrder": 5,
                        "hidden": False,
                    },
                    {
                        "value": YRS_EXPERIENCE_CHOICES[7][0],
                        "label": YRS_EXPERIENCE_CHOICES[7][1],
                        "displayOrder": 6,
                        "hidden": False,
                    },
                ],
            },
            {
                "name": "leadershiplevel",
                "label": "Leadership level",
                "description": "Leadership level",
                "groupName": "contactinformation",
                "type": "string",
                "fieldType": "text",
            },
            {
                "name": "highesteducation",
                "label": "Highest education",
                "description": "Highest level of education completed",
                "groupName": "contactinformation",
                "type": "enumeration",
                "fieldType": "select",
                "options": [
                    {
                        "value": HIGHEST_EDUCATION_CHOICES[1][0],
                        "label": HIGHEST_EDUCATION_CHOICES[1][1],
                        "displayOrder": 0,
                        "hidden": False,
                    },
                    {
                        "value": HIGHEST_EDUCATION_CHOICES[2][0],
                        "label": HIGHEST_EDUCATION_CHOICES[2][1],
                        "displayOrder": 1,
                        "hidden": False,
                    },
                    {
                        "value": HIGHEST_EDUCATION_CHOICES[3][0],
                        "label": HIGHEST_EDUCATION_CHOICES[3][1],
                        "displayOrder": 2,
                        "hidden": False,
                    },
                    {
                        "value": HIGHEST_EDUCATION_CHOICES[4][0],
                        "label": HIGHEST_EDUCATION_CHOICES[4][1],
                        "displayOrder": 3,
                        "hidden": False,
                    },
                    {
                        "value": HIGHEST_EDUCATION_CHOICES[5][0],
                        "label": HIGHEST_EDUCATION_CHOICES[5][1],
                        "displayOrder": 4,
                        "hidden": False,
                    },
                    {
                        "value": HIGHEST_EDUCATION_CHOICES[6][0],
                        "label": HIGHEST_EDUCATION_CHOICES[6][1],
                        "displayOrder": 5,
                        "hidden": False,
                    },
                    {
                        "value": HIGHEST_EDUCATION_CHOICES[7][0],
                        "label": HIGHEST_EDUCATION_CHOICES[7][1],
                        "displayOrder": 6,
                        "hidden": False,
                    },
                    {
                        "value": HIGHEST_EDUCATION_CHOICES[8][0],
                        "label": HIGHEST_EDUCATION_CHOICES[8][1],
                        "displayOrder": 7,
                        "hidden": False,
                    },
                    {
                        "value": HIGHEST_EDUCATION_CHOICES[9][0],
                        "label": HIGHEST_EDUCATION_CHOICES[9][1],
                        "displayOrder": 8,
                        "hidden": False,
                    },
                ],
            },
            {
                "name": "typeisstudent",
                "label": "Is student",
                "description": "Is a student",
                "groupName": "contactinformation",
                "type": "bool",
                "fieldType": "booleancheckbox",
                "options": [
                    {
                        "value": True,
                        "label": "True",
                        "displayOrder": 0,
                        "hidden": False,
                    },
                    {
                        "value": False,
                        "label": "False",
                        "displayOrder": 1,
                        "hidden": False,
                    },
                ],
            },
            {
                "name": "typeisprofessional",
                "label": "Is professional",
                "description": "Is a professional",
                "groupName": "contactinformation",
                "type": "bool",
                "fieldType": "booleancheckbox",
                "options": [
                    {
                        "value": True,
                        "label": "True",
                        "displayOrder": 0,
                        "hidden": False,
                    },
                    {
                        "value": False,
                        "label": "False",
                        "displayOrder": 1,
                        "hidden": False,
                    },
                ],
            },
            {
                "name": "typeiseducator",
                "label": "Is educator",
                "description": "Is a educator",
                "groupName": "contactinformation",
                "type": "bool",
                "fieldType": "booleancheckbox",
                "options": [
                    {
                        "value": True,
                        "label": "True",
                        "displayOrder": 0,
                        "hidden": False,
                    },
                    {
                        "value": False,
                        "label": "False",
                        "displayOrder": 1,
                        "hidden": False,
                    },
                ],
            },
            {
                "name": "typeisother",
                "label": "Is other",
                "description": "Is a other",
                "groupName": "contactinformation",
                "type": "bool",
                "fieldType": "booleancheckbox",
                "options": [
                    {
                        "value": True,
                        "label": "True",
                        "displayOrder": 0,
                        "hidden": False,
                    },
                    {
                        "value": False,
                        "label": "False",
                        "displayOrder": 1,
                        "hidden": False,
                    },
                ],
            },
        ],
    },
    "line_items": {
        "groups": [],
        "properties": [
            {
                "name": "status",
                "label": "Order Status",
                "description": "The current status of the order associated with the line item",
                "groupName": "lineiteminformation",
                "type": "enumeration",
                "fieldType": "select",
                "options": [
                    {
                        "value": models.OrderStatus.FULFILLED,
                        "label": models.OrderStatus.FULFILLED,
                        "displayOrder": 0,
                        "hidden": False,
                    },
                    {
                        "value": models.OrderStatus.CANCELED,
                        "label": models.OrderStatus.CANCELED,
                        "displayOrder": 1,
                        "hidden": False,
                    },
                    {
                        "value": models.OrderStatus.ERRORED,
                        "label": models.OrderStatus.ERRORED,
                        "displayOrder": 2,
                        "hidden": False,
                    },
                    {
                        "value": models.OrderStatus.DECLINED,
                        "label": models.OrderStatus.DECLINED,
                        "displayOrder": 3,
                        "hidden": False,
                    },
                    {
                        "value": models.OrderStatus.PENDING,
                        "label": models.OrderStatus.PENDING,
                        "displayOrder": 4,
                        "hidden": False,
                    },
                    {
                        "value": models.OrderStatus.REFUNDED,
                        "label": models.OrderStatus.REFUNDED,
                        "displayOrder": 5,
                        "hidden": False,
                    },
                    {
                        "value": models.OrderStatus.PARTIALLY_REFUNDED,
                        "label": models.OrderStatus.PARTIALLY_REFUNDED,
                        "displayOrder": 6,
                        "hidden": False,
                    },
                    {
                        "value": models.OrderStatus.REVIEW,
                        "label": models.OrderStatus.REVIEW,
                        "displayOrder": 7,
                        "hidden": False,
                    },
                ],
            },
            {
                "name": "unique_app_id",
                "label": "Unique App ID",
                "description": "The unique app ID for the lineitem",
                "groupName": "lineiteminformation",
                "type": "string",
                "fieldType": "text",
                "hasUniqueValue": True,
                "hidden": True,
            },
            {
                "name": "enrollment_mode",
                "label": "Enrollment Mode",
                "description": "The enrollment mode the user is currently enrolled into the product as.",
                "groupName": "lineiteminformation",
                "type": "enumeration",
                "fieldType": "select",
                "options": [
                    {
                        "value": EDX_ENROLLMENT_AUDIT_MODE,
                        "label": EDX_ENROLLMENT_AUDIT_MODE,
                        "displayOrder": 0,
                        "hidden": False,
                    },
                    {
                        "value": EDX_ENROLLMENT_VERIFIED_MODE,
                        "label": EDX_ENROLLMENT_VERIFIED_MODE,
                        "displayOrder": 1,
                        "hidden": False,
                    },
                ],
            },
            {
                "name": "change_status",
                "label": "Change Status",
                "description": "Any change in enrollment status.",
                "groupName": "lineiteminformation",
                "type": "enumeration",
                "fieldType": "select",
                "options": [
                    {
                        "value": ALL_ENROLL_CHANGE_STATUSES[0],
                        "label": ALL_ENROLL_CHANGE_STATUSES[0],
                        "displayOrder": 0,
                        "hidden": False,
                    },
                    {
                        "value": ALL_ENROLL_CHANGE_STATUSES[1],
                        "label": ALL_ENROLL_CHANGE_STATUSES[1],
                        "displayOrder": 1,
                        "hidden": False,
                    },
                    {
                        "value": ALL_ENROLL_CHANGE_STATUSES[2],
                        "label": ALL_ENROLL_CHANGE_STATUSES[2],
                        "displayOrder": 2,
                        "hidden": False,
                    },
                    {
                        "value": ALL_ENROLL_CHANGE_STATUSES[3],
                        "label": ALL_ENROLL_CHANGE_STATUSES[3],
                        "displayOrder": 3,
                        "hidden": False,
                    },
                ],
            },
        ],
    },
    "products": {
        "groups": [],
        "properties": [
            {
                "name": "unique_app_id",
                "label": "Unique App ID",
                "description": "The unique app ID for the product",
                "groupName": "productinformation",
                "type": "string",
                "fieldType": "text",
                "hasUniqueValue": True,
                "hidden": True,
            },
        ],
    },
}


def _get_course_run_certificate_hubspot_property():
    """
    Creates a dictionary representation of a Hubspot checkbox,
    populated with options using the string representation of all course runs.

    Returns:
        dict: dictionary representing the properties for a HubSpot checkbox,
        populated with the string representation of all course runs.
    """
    course_runs = CourseRun.objects.all()
    options_array = [
        {
            "value": str(course_run),
            "label": str(course_run),
            "hidden": False,
        }
        for course_run in course_runs
    ]
    return {
        "name": "course_run_certificates",
        "label": "Course Run certificates",
        "description": "Earned course run certificates.",
        "groupName": "contactinformation",
        "type": "enumeration",
        "fieldType": "checkbox",
        "options": options_array,
    }


def _get_program_certificate_hubspot_property():
    """
    Creates a dictionary representation of a Hubspot checkbox,
    populated with options using string representation of all programs.

    Returns:
        dict: dictionary representing the properties for a HubSpot checkbox,
        populated with the string representation of all programs.
    """
    programs = Program.objects.all()
    options_array = [
        {
            "value": str(program),
            "label": str(program),
            "hidden": False,
        }
        for program in programs
    ]
    return {
        "name": "program_certificates",
        "label": "Program certificates",
        "description": "Earned program certificates.",
        "groupName": "contactinformation",
        "type": "enumeration",
        "fieldType": "checkbox",
        "options": options_array,
    }


def upsert_custom_properties():
    """Create or update all custom properties and groups"""
    for ecommerce_object_type, ecommerce_object in CUSTOM_ECOMMERCE_PROPERTIES.items():
        for group in ecommerce_object["groups"]:
            sys.stdout.write(f"Adding group {group}\n")
            sync_property_group(ecommerce_object_type, group["name"], group["label"])
        for obj_property in ecommerce_object["properties"]:
            sys.stdout.write(f"Adding property {obj_property}\n")
            sync_object_property(ecommerce_object_type, obj_property)
    sync_object_property("contacts", _get_course_run_certificate_hubspot_property())
    sync_object_property("contacts", _get_program_certificate_hubspot_property())


def make_contact_create_message_list_from_user_ids(
    user_ids: List[int],  # noqa: UP006
) -> List[SimplePublicObjectInput]:  # noqa: UP006
    """
    Create the body of a HubSpot create message for a list of User IDs.

    Args:
        user_ids (List[int]): List of user ids.

    Returns:
        List[SimplePublicObjectInput]: List of input objects for upserting User data to Hubspot
    """
    users = list(
        User.objects.filter(id__in=user_ids).order_by("id")
    )  # Sorted to support unit test.
    message_list = []
    for user in users:
        message_list.append(make_contact_sync_message_from_user(user))  # noqa: PERF401

    return message_list


def make_contact_update_message_list_from_user_ids(
    chunk: List[tuple[int, str]],  # noqa: UP006
) -> List[dict]:  # noqa: UP006
    """
    Create the body of a HubSpot contact update message from a dictionary..

    Args:
        chunk (List[tuple(int, str)]): List of tuples of (User ID, HubSpot Object ID).

    Returns:
        List[dict]: List of dictionaries containing User properties.
    """
    chunk_dictionary = dict(chunk)
    users = User.objects.filter(id__in=chunk_dictionary.keys())
    request_input = []
    for user_id, hubspot_id in chunk_dictionary.items():
        user = users.filter(id=user_id).first()
        request_input.append(
            {
                "id": hubspot_id,
                "properties": make_contact_sync_message_from_user(user).properties,
            }
        )
    return request_input


def make_contact_sync_message_from_user(user: User) -> SimplePublicObjectInput:
    """
    Create the body of a HubSpot sync message for a contact. This will flatten the contained LegalAddress and Profile
    serialized data into one larger serializable dict

    Args:
        user (User): User object.
    Returns:
        SimplePublicObjectInput: Input object for upserting User data to Hubspot
    """
    from hubspot_sync.serializers import HubspotContactSerializer  # noqa: PLC0415

    contact_properties_map = {
        "email": "email",
        "name": "name",
        "country": "country",
        "state": "state",
        "year_of_birth": "yearofbirth",
        "gender": "gender",
        "company": "company",
        "company_size": "companysize",
        "job_title": "jobtitle",
        "industry": "industry",
        "job_function": "jobfunction",
        "years_experience": "yearsexperience",
        "leadership_level": "leadershiplevel",
        "highest_education": "highesteducation",
        "type_is_student": "typeisstudent",
        "type_is_professional": "typeisprofessional",
        "type_is_educator": "typeiseducator",
        "type_is_other": "typeisother",
        "program_certificates": "program_certificates",
        "course_run_certificates": "course_run_certificates",
    }
    properties = HubspotContactSerializer(user).data
    properties.update(properties.pop("legal_address") or {})
    properties.update(properties.pop("user_profile") or {})
    hubspot_props = transform_object_properties(properties, contact_properties_map)
    return make_object_properties_message(hubspot_props)


def make_deal_create_message_list_from_order_ids(
    order_ids: List[int],  # noqa: UP006
) -> SimplePublicObjectInput:
    """
    Create the body of a HubSpot Deal create message for a list of Order IDs.

    Args:
        order_ids (List[int]): List of Order ids.

    Returns:
        List[SimplePublicObjectInput]: List of input objects for upserting Order data to Hubspot
    """
    orders = Order.objects.filter(id__in=order_ids)
    message_list = []
    for order in orders:
        message_list.append(make_deal_sync_message_from_order(order))  # noqa: PERF401
    return message_list


def make_deal_update_message_list_from_order_ids(
    chunk: List[tuple[int, str]],  # noqa: UP006
) -> List[dict]:  # noqa: UP006
    """
    Create the body of a HubSpot Deal batch update message from a dictionary.

    Args:
        chunk (List[tuple(int, str)]): List of tuples of (Order ID, HubSpot Object ID).

    Returns:
        List[dict]: List of dictionaries containing Order properties.
    """
    chunk_dictionary = dict(chunk)
    orders = Order.objects.filter(id__in=chunk_dictionary.keys())
    request_input = []
    for order_id, hubspot_id in chunk_dictionary.items():
        order = orders.filter(id=order_id).first()
        request_input.append(
            {
                "id": hubspot_id,
                "properties": make_deal_sync_message_from_order(order).properties,
            }
        )
    return request_input


def make_deal_sync_message_from_order(order: Order) -> SimplePublicObjectInput:
    """
    Create a hubspot sync message for an Order.

    Args:
        order (Order): Order object.

    Returns:
        SimplePublicObjectInput: input object for upserting Order data to Hubspot
    """
    from hubspot_sync.serializers import OrderToDealSerializer  # noqa: PLC0415

    properties = OrderToDealSerializer(order).data
    return make_object_properties_message(properties)


def make_line_item_create_messages_list_from_line_ids(
    line_ids: List[int],  # noqa: UP006
) -> SimplePublicObjectInput:
    """
    Create the body of a HubSpot Line create message for a list of Line IDs.

    Args:
        line_ids (List[int]): List of Line ids.

    Returns:
        List[SimplePublicObjectInput]: List of input objects for upserting Line data to Hubspot
    """
    lines = Line.objects.filter(id__in=line_ids)
    message_list = []
    for line in lines:
        message_list.append(make_line_item_sync_message_from_line(line))  # noqa: PERF401
    return message_list


def make_line_item_update_message_list_from_line_ids(
    chunk: List[tuple[int, str]],  # noqa: UP006
) -> List[dict]:  # noqa: UP006
    """
    Create the body of a HubSpot Line batch update message from a dictionary.

    Args:
        chunk (List[tuple(int, str)]): List of tuples of (Line ID, HubSpot Object ID).

    Returns:
        List[dict]: List of dictionaries containing Line properties.
    """
    chunk_dictionary = dict(chunk)
    lines = Line.objects.filter(id__in=chunk_dictionary.keys())
    request_input = []
    for line_id, hubspot_id in chunk_dictionary.items():
        line = lines.filter(id=line_id).first()
        request_input.append(
            {
                "id": hubspot_id,
                "properties": make_line_item_sync_message_from_line(line).properties,
            }
        )
    return request_input


def make_line_item_sync_message_from_line(line: Line) -> SimplePublicObjectInput:
    """
    Create a hubspot sync input object for a Line.

    Args:
        line (Line): Line object.

    Returns:
        SimplePublicObjectInput: input object for upserting Line data to Hubspot
    """
    from hubspot_sync.serializers import LineSerializer  # noqa: PLC0415

    properties = LineSerializer(line).data
    return make_object_properties_message(properties)


def make_product_create_message_list_from_product_ids(
    product_ids: List[int],  # noqa: UP006
) -> SimplePublicObjectInput:
    """
    Create the body of a HubSpot Product create message for a list of Product IDs.

    Args:
        product_ids (List[int]): List of product ids.

    Returns:
        List[SimplePublicObjectInput]: List of input objects for createing Product data to Hubspot.
    """
    message_list = []
    products = Product.objects.filter(id__in=product_ids)
    for product in products:
        message_list.append(make_product_sync_message_from_product(product))  # noqa: PERF401
    return message_list


def make_product_update_message_list_from_product_ids(
    chunk: List[tuple[int, str]],  # noqa: UP006
) -> List[dict]:  # noqa: UP006
    """
    Create the body of a HubSpot Product batch update message from a dictionary.

    Args:
        chunk (List[tuple(int, str)]): List of tuples of (Product ID, HubSpot Object ID).

    Returns:
        List[dict]: List of dictionaries containing Product properties.
    """
    chunk_dictionary = dict(chunk)
    products = Product.objects.filter(id__in=chunk_dictionary.keys())
    request_input = []
    for product_id, hubspot_id in chunk_dictionary.items():
        product = products.filter(id=product_id).first()
        request_input.append(
            {
                "id": hubspot_id,
                "properties": make_product_sync_message_from_product(
                    product
                ).properties,
            }
        )
    return request_input


def make_product_sync_message_from_product(product: Product) -> SimplePublicObjectInput:
    """
    Create a hubspot sync input object for a Product.

    Args:
        product (Product): Product object.

    Returns:
        SimplePublicObjectInput: input object for upserting Product data to Hubspot
    """
    from hubspot_sync.serializers import ProductSerializer  # noqa: PLC0415

    properties = ProductSerializer(product).data
    return make_object_properties_message(properties)


def format_product_name(product: Product) -> str:
    """
    Get the Product name as it should appear in Hubspot

    Args:
        product(Product): The product to return a name for

    Returns:
        str: The name of the Product as it should appear in Hubspot
    """
    product_obj = product.purchasable_object
    title_run_id = re.findall(r"\+R(\d+)$", product_obj.readable_id)
    title_suffix = f"Run {title_run_id[0]}" if title_run_id else product_obj.readable_id
    return f"{product_obj.title}: {title_suffix} [{format_app_id(product.id)}]"


def sync_contact_hubspot_ids_to_db():
    """
    Create HubspotObjects for all contacts in Hubspot

    Returns:
        bool: True if hubspot id matches found for all Users
    """
    contacts = get_all_objects(
        HubspotObjectType.CONTACTS.value, properties=["email", "hs_additional_emails"]
    )
    content_type = ContentType.objects.get_for_model(User)
    for contact in contacts:
        user = User.objects.filter(email__iexact=contact.properties["email"]).first()
        if not user and contact.properties["hs_additional_emails"]:
            alt_email_q = Q()
            for alt_email in contact.properties["hs_additional_emails"].split(";"):
                alt_email_q |= Q(email__iexact=alt_email)
            user = User.objects.filter(alt_email_q).first()
        if user:
            HubspotObject.objects.update_or_create(
                content_type=content_type,
                object_id=user.id,
                defaults={"hubspot_id": contact.id},
            )
    return (
        User.objects.count()
        == HubspotObject.objects.filter(content_type=content_type).count()
    )


def sync_product_hubspot_ids_to_db() -> bool:
    """
    Create HubspotObjects for products, return True if all products have hubspot ids

    Returns:
        bool: True if hubspot id matches found for all Products
    """
    content_type = ContentType.objects.get_for_model(Product)
    product_mapping = {}
    for product in Product.objects.all():
        product_mapping.setdefault(format_product_name(product), []).append(product.id)
    products = get_all_objects(HubspotObjectType.PRODUCTS.value)
    for product in products:
        matching_products = product_mapping.get(product.properties["name"])
        if not matching_products:
            continue
        if len(matching_products) > 1:
            # Narrow down by price
            matched_subquery = HubspotObject.objects.filter(
                content_type=content_type
            ).values_list("object_id", flat=True)
            matching_product = (
                Product.objects.exclude(id__in=matched_subquery)
                .filter(
                    id__in=matching_products,
                    price=Decimal(product.properties["price"]),
                )
                .order_by("-created_on")
                .values_list("id", flat=True)
                .first()
            )
        else:
            matching_product = matching_products[0]
        if matching_product:
            HubspotObject.objects.update_or_create(
                content_type=content_type,
                object_id=matching_product,
                defaults={"hubspot_id": product.id},
            )
    return (
        Product.objects.count()
        == HubspotObject.objects.filter(content_type=content_type).count()
    )


def sync_deal_hubspot_ids_to_db() -> bool:
    """
    Create Hubspot objects for orders and lines, return True if all orders
    (and optionally lines) have hubspot ids

    Returns:
        bool: True if matches found for all Orders (and optionally their lines)
    """
    ct_order = ContentType.objects.get_for_model(Order)
    deals = get_all_objects(
        HubspotObjectType.DEALS.value, properties=["dealname", "amount"]
    )
    lines_synced = True
    for deal in deals:
        deal_name = deal.properties["dealname"]
        deal_price = Decimal(deal.properties["amount"] or "0.00")
        try:
            object_id = int(deal_name.split("-")[-1])
        except ValueError:
            # this isn't a deal that can be synced, ie "AMx Run 3 - SPIN MASTER"
            continue
        order = Order.objects.filter(id=object_id, total_price_paid=deal_price).first()
        content_type = ct_order
        if order:
            HubspotObject.objects.update_or_create(
                content_type=content_type,
                object_id=order.id,
                defaults={"hubspot_id": deal.id},
            )
            if not sync_deal_line_hubspot_ids_to_db(order, deal.id):
                lines_synced = False
    return (Order.objects.count()) == HubspotObject.objects.filter(
        content_type=ct_order
    ).count() and lines_synced


def sync_deal_line_hubspot_ids_to_db(order, hubspot_order_id) -> bool:
    """
    Create HubspotObjects for all of a deal's line items, return True if matches found for all lines

    Args:
        order(Order): The order to sync Hubspot line items for
        hubspot_order_id(str): The Hubspot deal id

    Returns:
        bool: True if matches found for all the order lines

    """
    line_items = get_line_items_for_deal(hubspot_order_id)
    order_line = order.lines.first()

    matches = 0
    expected_matches = order.lines.count()
    if len(line_items) == 1:
        HubspotObject.objects.update_or_create(
            content_type=ContentType.objects.get_for_model(order_line),
            object_id=order_line.id,
            defaults={"hubspot_id": line_items[0].id},
        )
        matches += 1
    else:  # Multiple lines, need to match by product and quantity
        for line in line_items:
            hs_product = HubspotObject.objects.filter(
                hubspot_id=line.properties["hs_product_id"],
                content_type=ContentType.objects.get_for_model(Product),
            ).first()
            if hs_product:
                product_id = hs_product.object_id
                matching_line = Line.objects.filter(
                    order=order,
                    product_version__object_id=product_id,
                    quantity=int(line.properties["quantity"]),
                ).first()
                if matching_line:
                    HubspotObject.objects.update_or_create(
                        content_type=ContentType.objects.get_for_model(Line),
                        object_id=matching_line.id,
                        defaults={"hubspot_id": line.id},
                    )
                    matches += 1
    return matches == expected_matches


def get_hubspot_id_for_object(  # noqa: C901
    obj: Order or Product or Line or User,
    raise_error: bool = False,  # noqa: FBT001, FBT002
) -> str:
    """
    Get the hubspot id for an object, querying Hubspot if necessary

    Args:
        obj(object): The object (Order, Product, Line, or User) to get the id for
        raise_error(bool): raise an error if not found (default False)

    Returns:
        The hubspot id for the object if it has been previously synced to Hubspot.
        Raises a ValueError if no matching Hubspot object can be found.
    """
    from hubspot_sync.serializers import get_hubspot_serializer  # noqa: PLC0415

    content_type = ContentType.objects.get_for_model(obj)
    hubspot_obj = HubspotObject.objects.filter(
        object_id=obj.id, content_type=content_type
    ).first()
    if hubspot_obj:
        return hubspot_obj.hubspot_id
    if isinstance(obj, User):
        try:
            hubspot_obj = find_contact(obj.email)
        except:  # noqa: E722
            log.exception(f"No User found w/ {obj.email}, is it active?")  # noqa: G004
    elif isinstance(obj, Order):
        serialized_deal = get_hubspot_serializer(obj).data
        hubspot_obj = find_deal(
            name=serialized_deal["dealname"],
            amount=serialized_deal["amount"],
            raise_count_error=raise_error,
        )
    elif isinstance(obj, Line):
        serialized_line = get_hubspot_serializer(obj).data
        order_id = get_hubspot_id_for_object(obj.order)
        if order_id:
            hubspot_obj = find_line_item(
                order_id,
                quantity=serialized_line["quantity"],
                hs_product_id=serialized_line["hs_product_id"],
                raise_count_error=raise_error,
            )
    elif isinstance(obj, Product):
        serialized_product = get_hubspot_serializer(obj).data
        hubspot_obj = find_product(
            serialized_product["name"],
            raise_count_error=raise_error,
        )
    if hubspot_obj and hubspot_obj.id:
        try:
            HubspotObject.objects.update_or_create(
                object_id=obj.id,
                content_type=content_type,
                defaults={"hubspot_id": hubspot_obj.id},
            )
        except:
            log.error(  # noqa: TRY400
                f"OBJ_ID: {obj.id}, ct: {content_type}, hubspot_id: {hubspot_obj.id}"  # noqa: G004
            )
            raise
        return hubspot_obj.id
    elif raise_error:
        msg = f"Hubspot id could not be found for {content_type.name} for id {obj.id}"
        raise ValueError(msg)

    return None


def sync_line_item_with_hubspot(line: Line) -> SimplePublicObject:
    """
    Sync a Line with a hubspot line item

    Args:
        line(Line): The Line object.

    Returns:
        SimplePublicObject: The hubspot line_item object
    """
    body = make_line_item_sync_message_from_line(line)
    content_type = ContentType.objects.get_for_model(Line)

    # Check if a matching hubspot object has been or can be synced
    get_hubspot_id_for_object(line)

    # Apply rate limiting before making the request
    wait_for_hubspot_rate_limit()

    # Create or update the line items
    result = upsert_object_request(
        content_type, HubspotObjectType.LINES.value, object_id=line.id, body=body
    )
    # Associate the parent deal with the line item
    associate_objects_request(
        HubspotObjectType.LINES.value,
        result.id,
        HubspotObjectType.DEALS.value,
        get_hubspot_id_for_object(line.order),
        HubspotAssociationType.LINE_DEAL.value,
    )
    return result


def sync_deal_with_hubspot(order: Order) -> SimplePublicObject:
    """
    Sync an Order with a hubspot deal

    Args:
        order (Order): The Order object.

    Returns:
        SimplePublicObject: The hubspot deal object
    """
    body = make_deal_sync_message_from_order(order)
    content_type = ContentType.objects.get_for_model(Order)

    # Check if a matching hubspot object has been or can be synced
    get_hubspot_id_for_object(order)

    # Apply rate limiting before making the request
    wait_for_hubspot_rate_limit()

    # Create or update the order aka deal
    result = upsert_object_request(
        content_type, HubspotObjectType.DEALS.value, object_id=order.id, body=body
    )
    # Create association between deal and contact
    associate_objects_request(
        HubspotObjectType.DEALS.value,
        result.id,
        HubspotObjectType.CONTACTS.value,
        get_hubspot_id_for_object(order.purchaser),
        HubspotAssociationType.DEAL_CONTACT.value,
    )

    for line in order.lines.all():
        sync_line_item_with_hubspot(line)
    return result


def sync_product_with_hubspot(product: Product) -> SimplePublicObject:
    """
    Sync a Product with a hubspot product

    Args:
        product(Product): The Product object.

    Returns:
        SimplePublicObject: The hubspot product object.
    """
    body = make_product_sync_message_from_product(product)
    content_type = ContentType.objects.get_for_model(Product)

    # Apply rate limiting before making the request
    wait_for_hubspot_rate_limit()

    return upsert_object_request(
        content_type, HubspotObjectType.PRODUCTS.value, object_id=product.id, body=body
    )


def sync_contact_with_hubspot(user: User):
    """
    Sync a user with a hubspot_sync contact.

    Args:
        user User: User object.

    Returns:
        SimplePublicObject: The hubspot contact object.

    Raises:
        ApiException: Raised if HubSpot upsert request fails.
        TooManyRequestsException: Too many requests against HubSpot's API.
    """
    content_type = ContentType.objects.get_for_model(User)
    body = make_contact_sync_message_from_user(user)

    # Apply rate limiting before making the request
    wait_for_hubspot_rate_limit()

    result = upsert_object_request(
        content_type,
        HubspotObjectType.CONTACTS.value,
        object_id=user.id,
        body=body,
    )
    user.hubspot_sync_datetime = now_in_utc()
    user.save(update_fields=["hubspot_sync_datetime"])

    return result


MODEL_CREATE_FUNCTION_MAPPING = {
    "user": make_contact_create_message_list_from_user_ids,
    "order": make_deal_create_message_list_from_order_ids,
    "line": make_line_item_create_messages_list_from_line_ids,
    "product": make_product_create_message_list_from_product_ids,
}

MODEL_UPDATE_FUNCTION_MAPPING = {
    "user": make_contact_update_message_list_from_user_ids,
    "order": make_deal_update_message_list_from_order_ids,
    "line": make_line_item_update_message_list_from_line_ids,
    "product": make_product_update_message_list_from_product_ids,
}
