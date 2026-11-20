"""Factories for the location app."""

from factory import Faker
from factory.django import DjangoModelFactory
from factory.fuzzy import FuzzyChoice

from location.constants import LOCATION_FLAG_RULES, LOCATION_FLAG_TYPES
from location.models import LocationFlag


class LocationFlagFactory(DjangoModelFactory):
    """Factory for LocationFlag"""

    flag_type = FuzzyChoice(LOCATION_FLAG_TYPES)
    determination_rule = FuzzyChoice(LOCATION_FLAG_RULES)
    country_code = Faker("country_code", representation="alpha-2")

    class Meta:
        model = LocationFlag
