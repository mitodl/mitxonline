"""Models for locations."""

import reversion
from django.db import models
from django_countries.fields import CountryField
from mitol.common.models import TimestampedModel, TimestampedModelQuerySet
from mitol.common.utils.datetime import now_in_utc

from location.constants import (
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
