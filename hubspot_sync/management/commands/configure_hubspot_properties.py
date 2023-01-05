"""
Management command to configure custom Hubspot properties for Contacts, Deals, Products, and Line Items
"""
import sys

from django.core.management import BaseCommand
from mitol.hubspot_api.api import (
    delete_object_property,
    delete_property_group,
    object_property_exists,
    property_group_exists,
    sync_object_property,
    sync_property_group,
)

from ecommerce import models
from ecommerce.constants import (
    DISCOUNT_TYPE_DOLLARS_OFF,
    DISCOUNT_TYPE_FIXED_PRICE,
    DISCOUNT_TYPE_PERCENT_OFF,
)

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
                        "value": models.Order.STATE.FULFILLED,
                        "label": models.Order.STATE.FULFILLED,
                        "displayOrder": 0,
                        "hidden": False,
                    },
                    {
                        "value": models.Order.STATE.CANCELED,
                        "label": models.Order.STATE.CANCELED,
                        "displayOrder": 1,
                        "hidden": False,
                    },
                    {
                        "value": models.Order.STATE.ERRORED,
                        "label": models.Order.STATE.ERRORED,
                        "displayOrder": 2,
                        "hidden": False,
                    },
                    {
                        "value": models.Order.STATE.DECLINED,
                        "label": models.Order.STATE.DECLINED,
                        "displayOrder": 3,
                        "hidden": False,
                    },
                    {
                        "value": models.Order.STATE.PENDING,
                        "label": models.Order.STATE.PENDING,
                        "displayOrder": 4,
                        "hidden": False,
                    },
                    {
                        "value": models.Order.STATE.REFUNDED,
                        "label": models.Order.STATE.REFUNDED,
                        "displayOrder": 5,
                        "hidden": False,
                    },
                    {
                        "value": models.Order.STATE.PARTIALLY_REFUNDED,
                        "label": models.Order.STATE.PARTIALLY_REFUNDED,
                        "displayOrder": 6,
                        "hidden": False,
                    },
                    {
                        "value": models.Order.STATE.REVIEW,
                        "label": models.Order.STATE.REVIEW,
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
                        "value": models.Order.STATE.FULFILLED,
                        "label": models.Order.STATE.FULFILLED,
                        "displayOrder": 0,
                        "hidden": False,
                    },
                    {
                        "value": models.Order.STATE.CANCELED,
                        "label": models.Order.STATE.CANCELED,
                        "displayOrder": 1,
                        "hidden": False,
                    },
                    {
                        "value": models.Order.STATE.ERRORED,
                        "label": models.Order.STATE.ERRORED,
                        "displayOrder": 1,
                        "hidden": False,
                    },
                    {
                        "value": models.Order.STATE.DECLINED,
                        "label": models.Order.STATE.DECLINED,
                        "displayOrder": 1,
                        "hidden": False,
                    },
                    {
                        "value": models.Order.STATE.PENDING,
                        "label": models.Order.STATE.PENDING,
                        "displayOrder": 0,
                        "hidden": False,
                    },
                    {
                        "value": models.Order.STATE.REFUNDED,
                        "label": models.Order.STATE.REFUNDED,
                        "displayOrder": 1,
                        "hidden": False,
                    },
                    {
                        "value": models.Order.STATE.PARTIALLY_REFUNDED,
                        "label": models.Order.STATE.PARTIALLY_REFUNDED,
                        "displayOrder": 1,
                        "hidden": False,
                    },
                    {
                        "value": models.Order.STATE.REVIEW,
                        "label": models.Order.STATE.REVIEW,
                        "displayOrder": 1,
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


def upsert_custom_properties():
    """Create or update all custom properties and groups"""
    for object_type in CUSTOM_ECOMMERCE_PROPERTIES:
        for group in CUSTOM_ECOMMERCE_PROPERTIES[object_type]["groups"]:
            sys.stdout.write(f"Adding group {group}\n")
            sync_property_group(object_type, group["name"], group["label"])
        for obj_property in CUSTOM_ECOMMERCE_PROPERTIES[object_type]["properties"]:
            sys.stdout.write(f"Adding property {obj_property}\n")
            sync_object_property(object_type, obj_property)


def delete_custom_properties():
    """Delete all custom properties and groups"""
    for object_type in CUSTOM_ECOMMERCE_PROPERTIES:
        for obj_property in CUSTOM_ECOMMERCE_PROPERTIES[object_type]["properties"]:
            if object_property_exists(object_type, obj_property):
                delete_object_property(object_type, obj_property)
        for group in CUSTOM_ECOMMERCE_PROPERTIES[object_type]["groups"]:
            if property_group_exists(object_type, group):
                delete_property_group(object_type, group)


class Command(BaseCommand):
    """
    Command to create/update or delete custom hubspot object properties and property groups
    """

    help = "Upsert or delete custom properties and property groups for Hubspot objects"

    def add_arguments(self, parser):
        """
        Definition of arguments this command accepts
        """
        parser.add_argument(
            "--delete",
            action="store_true",
            help="Delete custom hubspot properties/groups",
        )

    def handle(self, *args, **options):
        if options["delete"]:
            print("Uninstalling custom groups and properties...")
            delete_custom_properties()
            print("Uninstall successful")
            return
        else:
            print("Configuring custom groups and properties...")
            upsert_custom_properties()
            print("Custom properties configured")
