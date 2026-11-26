"""Models for locations."""

from dataclasses import asdict

import reversion
from django.db import models
from django_countries.fields import CountryField
from mitol.common.models import TimestampedModel, TimestampedModelQuerySet
from mitol.common.utils.datetime import now_in_utc

from location.constants import (
    GEOLOCATION_TYPE_CHOICES,
    GEOLOCATION_TYPE_GEOIP,
    GEOLOCATION_TYPE_NONE,
    GEOLOCATION_TYPE_PROFILE,
    LOCATION_FLAG_RULE_CHOICES,
    LOCATION_FLAG_RULE_DEFINITIONS,
    LOCATION_FLAG_TYPE_CHOICES,
)
from location.dataclasses import UserCalculatedLocation
from main.models import ValidateOnSaveMixin


class SoftDeleteQuerySet(TimestampedModelQuerySet):
    """QuerySet that soft-deletes instead of removing rows.

    Based on TimestampedModelQuerySet so update() (and so delete()) bump updated_on.
    """

    def delete(self):
        """Mark the matched rows inactive rather than deleting them."""

        return self.update(is_active=False, deleted_on=now_in_utc())


class ActiveObjectManager(models.Manager.from_queryset(SoftDeleteQuerySet)):
    """Query manager for active objects"""

    def get_queryset(self):
        """Getting the active queryset for manager"""
        return super().get_queryset().filter(is_active=True)


class SoftDeleteTimestampedModel(TimestampedModel):
    """Extends TimestampedModel to include a delete date and soft-deletion"""

    deleted_on = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(blank=True, default=True)

    objects = ActiveObjectManager()
    all_objects = SoftDeleteQuerySet.as_manager()

    def clean(self):
        """Keep deleted_on in sync with is_active."""

        if not self.is_active and not self.deleted_on:
            self.deleted_on = now_in_utc()
        elif self.is_active:
            self.deleted_on = None

        super().clean()

    def delete(self, using=None, keep_parents=False):  # noqa: ARG002, FBT002
        """Disallow deletion; change the is_active flag instead."""

        self.is_active = False
        self.deleted_on = now_in_utc()
        self.save(
            using=using,
            update_fields=(
                "is_active",
                "deleted_on",
                "updated_on",
            ),
        )
        return 1, {self._meta.label: 1}

    class Meta:
        """Flag this model as abstract."""

        abstract = True


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
        blank=False,
        choices=LOCATION_FLAG_TYPE_CHOICES,
    )
    determination_rule = models.CharField(
        help_text="The rule to use when determining flag state for a user.",
        max_length=100,
        choices=LOCATION_FLAG_RULE_CHOICES,
        blank=False,
    )
    country_code = CountryField()
    subdivision_1_code = models.CharField(
        help_text="ISO-3166-2 code for the first-level subdivison of the Country (region/county/etc), without alpha-2 prefix. Not yet used by any determination rule.",
        max_length=3,
        blank=True,
        default="",
    )
    subdivision_2_code = models.CharField(
        help_text="ISO-3166-2 code for the second-level subdivison of the Country (city/town/etc), without alpha-2 prefix. Not yet used by any determination rule.",
        max_length=3,
        blank=True,
        default="",
    )

    class Meta:
        """Only allow one active flag per type, rule, and location."""

        constraints = [
            models.UniqueConstraint(
                fields=(
                    "flag_type",
                    "determination_rule",
                    "country_code",
                    "subdivision_1_code",
                    "subdivision_2_code",
                ),
                condition=models.Q(is_active=True),
                name="location_flag_unique_active",
            ),
        ]

    def evaluate(self, location_data: list[UserCalculatedLocation]) -> bool:
        """
        Determine whether this flag is set for the given location data.

        The flag's determination_rule maps to a LocationFlagRule (see
        LOCATION_FLAG_RULE_DEFINITIONS) that says which location types to
        consider and whether any or all of them must match the flag's country.
        """

        rule = LOCATION_FLAG_RULE_DEFINITIONS.get(self.determination_rule)

        if rule is None:
            msg = f"Rule {self.determination_rule} has no rule definition."
            raise ValueError(msg)

        locations = [
            location
            for location in location_data
            if rule.lookup_types is None or location.lookup_type in rule.lookup_types
        ]

        if rule.require_all_types and not all(
            any(location.lookup_type == lookup_type for location in locations)
            for lookup_type in rule.lookup_types
        ):
            return False

        decisions = [
            location.country_code == self.country_code for location in locations
        ]

        if rule.match_all:
            return bool(decisions) and all(decisions)

        return any(decisions)


class UserLocationModel(models.Model):
    """
    Records where we determined the user was.

    Holds the location data as values rather than links, so the record says
    where we placed the user at the time even if their profile changes later.

    - location_country_code / location_source: the location we settled on and
      how we found it. GeoIP wins over the profile, since it says where the
      user is now.
    - location_data: every location we found, so location flag rules (which
      can need more than one source) can be checked against the record later.
    """

    location_country_code = CountryField(blank=True, default="")
    location_source = models.CharField(
        help_text="How the location was determined.",
        max_length=20,
        choices=GEOLOCATION_TYPE_CHOICES,
        default=GEOLOCATION_TYPE_NONE,
    )
    location_data = models.JSONField(
        help_text="Every location found for the user, with its source.",
        default=list,
        blank=True,
    )
    location_determined_on = models.DateTimeField(null=True, blank=True)

    LOCATION_FIELDS = (
        "location_country_code",
        "location_source",
        "location_data",
        "location_determined_on",
    )

    class Meta:
        """Flag this model as abstract."""

        abstract = True

    def set_location(self, locations: list[UserCalculatedLocation]):
        """
        Record the locations found for the user. Doesn't save.

        Args:
        - locations (list[UserCalculatedLocation]): from determine_user_location
        """

        by_type = {location.lookup_type: location for location in locations}
        primary = by_type.get(GEOLOCATION_TYPE_GEOIP) or by_type.get(
            GEOLOCATION_TYPE_PROFILE
        )

        self.location_country_code = (
            primary.country_code if primary and primary.country_code else ""
        )
        self.location_source = (
            primary.lookup_type
            if primary and primary.country_code
            else GEOLOCATION_TYPE_NONE
        )
        self.location_data = [asdict(location) for location in locations]
        self.location_determined_on = now_in_utc()

    def copy_location_from(self, other: "UserLocationModel | None"):
        """Copy the location fields from another record, if given. Doesn't save."""

        if other is None:
            return

        for field in self.LOCATION_FIELDS:
            setattr(self, field, getattr(other, field))

    @property
    def user_locations(self) -> list[UserCalculatedLocation]:
        """Return the recorded locations, for LocationFlag.evaluate."""

        return [UserCalculatedLocation(**location) for location in self.location_data]
