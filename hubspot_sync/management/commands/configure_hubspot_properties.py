"""
Management command to configure custom Hubspot properties for Contacts, Deals, Products, and Line Items
"""

import sys

from django.core.management import BaseCommand
from hubspot_sync.api import CUSTOM_ECOMMERCE_PROPERTIES, upsert_custom_properties
from hubspot_sync.api import upsert_custom_properties
from mitol.hubspot_api.api import (
    delete_object_property,
    delete_property_group,
    object_property_exists,
    property_group_exists,
)


def _delete_custom_properties():
    """Delete all custom properties and groups"""
    for ecommerce_object_type, ecommerce_object in CUSTOM_ECOMMERCE_PROPERTIES.items():
        for obj_property in ecommerce_object["properties"]:
            if object_property_exists(ecommerce_object_type, obj_property):
                delete_object_property(ecommerce_object_type, obj_property)
        for group in ecommerce_object["groups"]:
            if property_group_exists(ecommerce_object_type, group):
                delete_property_group(ecommerce_object_type, group)


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

    def handle(self, *args, **options):  # noqa: ARG002
        if options["delete"]:
            print("Uninstalling custom groups and properties...")  # noqa: T201
            _delete_custom_properties()
            print("Uninstall successful")  # noqa: T201
            return
        else:
            print("Configuring custom groups and properties...")  # noqa: T201
            upsert_custom_properties()
            print("Custom properties configured")  # noqa: T201
