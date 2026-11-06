"""Models for locations."""

import reversion
from django.db import models
from django_countries.fields import CountryField
from mitol.common.models import TimestampedModel
from mitol.common.utils.datetime import now_in_utc

from location.constants import (
    GEOLOCATION_TYPE_GEOIP,
    GEOLOCATION_TYPE_PROFILE,
    LOCATION_FLAG_RULE_CHOICES,
    LOCATION_FLAG_RULE_ONLY_GEOIP,
    LOCATION_FLAG_RULE_ONLY_PROFILE,
    LOCATION_FLAG_RULE_REQUIRE_ANY,
    LOCATION_FLAG_RULE_REQUIRE_PROFILE_GEOIP,
    LOCATION_FLAG_TYPE_CHOICES,
)
from location.dataclasses import UserCalculatedLocation
from main.models import ValidateOnSaveMixin


class ActiveObjectManager(models.Manager):
    """Query manager for active objects"""

    def get_queryset(self):
        """Getting the active queryset for manager"""
        return super().get_queryset().filter(is_active=True)


class SoftDeleteTimestampedModel(TimestampedModel):
    """Extends TimestampedModel to include a delete date and soft-deletion"""

    deleted_on = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(blank=True, default=True)

    objects = ActiveObjectManager()
    all_objects = models.Manager()

    def clean(self):
        """Ensure the deleted_on field is set if is_active=False."""

        if not self.is_active and not self.deleted_on:
            self.deleted_on = now_in_utc()

        super().clean()

    def delete(self, *_):
        """Disallow deletion; change the is_active flag instead."""

        self.is_active = False
        self.deleted_on = now_in_utc()
        self.save(
            updated_fields=(
                "is_active",
                "deleted_on",
            )
        )


@reversion.register(exclude=("created_on", "updated_on"))
class LocationFlag(SoftDeleteTimestampedModel, ValidateOnSaveMixin):
    """
    Stores locations that are flagged for special processing.

    Not intended to store anything specific about the processing - just that
    processing _should_ happen if there's a flag.
    """

    flag_type = models.CharField(
        help_text="Specifies what processing should happen if flagged.",
        max_length=100,
        blank=True,
        choices=LOCATION_FLAG_TYPE_CHOICES,
        default="",
    )
    determination_rule = models.CharField(
        help_text="The rule to use when determining flag state for a user.",
        max_length=100,
        choices=LOCATION_FLAG_RULE_CHOICES,
        blank=False,
    )
    country_code = CountryField()
    subdivision_1_code = models.CharField(
        help_text="ISO-3166-2 code for the first-level subdivison of the Country (region/county/etc), without alpha-2 prefix.",
        max_length=3,
        blank=True,
        default="",
    )
    subdivision_2_code = models.CharField(
        help_text="ISO-3166-2 code for the second-level subdivison of the Country (city/town/etc), without alpha-2 prefix.",
        max_length=3,
        blank=True,
        default="",
    )

    def evaluate(self, location_data: list[UserCalculatedLocation]):
        """Get the appropriate rule model, return is_applicable."""

        if not self.pk:
            # We're not saved yet so we can't re-retrieve as the proxy model.
            # Default to False in this case.
            return False

        rule_model = LocationFlag.get_rule_model_for_object(self)
        return rule_model.is_applicable(location_data)

    @staticmethod
    def get_rule_model_for_object(location_flag):
        """Get the rule model for the specified type."""

        mapping = {
            LOCATION_FLAG_RULE_ONLY_PROFILE: OnlyProfileLocationFlag,
            LOCATION_FLAG_RULE_ONLY_GEOIP: OnlyGeoIPLocationFlag,
            LOCATION_FLAG_RULE_REQUIRE_PROFILE_GEOIP: ProfileAndGeoIPLocationFlag,
            LOCATION_FLAG_RULE_REQUIRE_ANY: MatchAnyLocationFlag,
        }

        if location_flag.determination_rule not in mapping:
            msg = f"Rule {location_flag.determination_rule} has no rule model."
            raise ValueError(msg)

        return mapping[location_flag.determination_rule].objects.get(
            pk=location_flag.pk
        )


# Rule Models


class OnlyProfileLocationFlag(LocationFlag):
    """Implements the rules for profile-only flags."""

    def is_applicable(self, location_data: list[UserCalculatedLocation]):
        """If the user profile matches the flag's country, then the flag is set."""

        decisions = [
            (
                ld.lookup_type == GEOLOCATION_TYPE_PROFILE
                and ld.country_code == self.country_code
            )
            for ld in location_data
        ]

        return all(decisions)

    class Meta:
        """Set the model as a proxy."""

        proxy = True


class OnlyGeoIPLocationFlag(LocationFlag):
    """Implements the rules for GeoIP-only flags."""

    def is_applicable(self, location_data: list[UserCalculatedLocation]):
        """If the GeoIP location matches the flag's country, then the flag is set."""

        decisions = [
            (
                ld.lookup_type == GEOLOCATION_TYPE_GEOIP
                and ld.country_code == self.country_code
            )
            for ld in location_data
        ]

        return all(decisions)

    class Meta:
        """Set the model as a proxy."""

        proxy = True


class ProfileAndGeoIPLocationFlag(LocationFlag):
    """Implements the rules for profile-and-GeoIP flags."""

    def is_applicable(self, location_data: list[UserCalculatedLocation]):
        """If the user profile matches the flag's country, then the flag is set."""

        decisions = [
            (
                ld.lookup_type
                in (
                    GEOLOCATION_TYPE_PROFILE,
                    GEOLOCATION_TYPE_GEOIP,
                )
                and ld.country_code == self.country_code
            )
            for ld in location_data
        ]

        return all(decisions)

    class Meta:
        """Set the model as a proxy."""

        proxy = True


class MatchAnyLocationFlag(LocationFlag):
    """Implements the rules for profile-and-GeoIP flags."""

    def is_applicable(self, location_data: list[UserCalculatedLocation]):
        """If the user profile matches the flag's country, then the flag is set."""

        decisions = [(ld.country_code == self.country_code) for ld in location_data]

        return all(decisions)

    class Meta:
        """Set the model as a proxy."""

        proxy = True
