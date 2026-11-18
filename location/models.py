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
    LOCATION_FLAG_RULE_MATCH_ALL,
    LOCATION_FLAG_RULE_MATCH_ANY,
    LOCATION_FLAG_RULE_MATCH_GEOIP_ANY,
    LOCATION_FLAG_RULE_MATCH_PROFILE_ALL,
    LOCATION_FLAG_RULE_MATCH_PROFILE_ANY,
    LOCATION_FLAG_RULE_MATCH_PROFILE_GEOIP_ALL,
    LOCATION_FLAG_RULE_MATCH_PROFILE_GEOIP_ANY,
    LOCATION_FLAG_RULE_REQUIRE_PROFILE_GEOIP_MATCH_ALL,
    LOCATION_FLAG_TYPE_CHOICES,
)
from location.dataclasses import UserCalculatedLocation
from main.models import ValidateOnSaveMixin


class SoftDeleteQuerySet(models.QuerySet):
    """QuerySet that soft-deletes instead of removing rows."""

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
        """Ensure the deleted_on field is set if is_active=False."""

        if not self.is_active and not self.deleted_on:
            self.deleted_on = now_in_utc()

        super().clean()

    def delete(self, *_):
        """Disallow deletion; change the is_active flag instead."""

        self.is_active = False
        self.deleted_on = now_in_utc()
        self.save(
            update_fields=(
                "is_active",
                "deleted_on",
            )
        )

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
            LOCATION_FLAG_RULE_MATCH_PROFILE_ANY: ProfileMatchAnyLocationFlag,
            LOCATION_FLAG_RULE_MATCH_PROFILE_ALL: ProfileMatchAllLocationFlag,
            LOCATION_FLAG_RULE_MATCH_GEOIP_ANY: GeoIPMatchAnyLocationFlag,
            LOCATION_FLAG_RULE_MATCH_PROFILE_GEOIP_ANY: ProfileAndGeoIPMatchAnyLocationFlag,
            LOCATION_FLAG_RULE_MATCH_PROFILE_GEOIP_ALL: ProfileAndGeoIPMatchAllLocationFlag,
            LOCATION_FLAG_RULE_MATCH_ANY: AnyTypeMatchAnyLocationFlag,
            LOCATION_FLAG_RULE_MATCH_ALL: AnyTypeMatchAllLocationFlag,
            LOCATION_FLAG_RULE_REQUIRE_PROFILE_GEOIP_MATCH_ALL: RequireProfileGeoIPMatchAllLocationFlag,
        }

        if location_flag.determination_rule not in mapping:
            msg = f"Rule {location_flag.determination_rule} has no rule model."
            raise ValueError(msg)

        return mapping[location_flag.determination_rule].all_objects.get(
            pk=location_flag.pk
        )


# Rule Models
# These are named for what they do, in this general format:
#   LocationTypeMatchSetLocationFlag
# so ProfileMatchAnyLocationFlag means "using user's profile, match if any
# location matches".


class ProfileMatchAnyLocationFlag(LocationFlag):
    """
    Implements the rules for profile-only flags.

    Rule:
        - Types: Profile (LegalAddress) only
        - Matches: Any
        - Default: Flag Not Set

        For only the location data derived from the user's profile, set the flag
        if any locations match the flag location. If there are no matches or the
        user has no applicable location data, the flag is not set.

    In practice, this should only ever consider a single location, because this
    app only allows a single LegalAddress for a given User.
    """

    def is_applicable(self, location_data: list[UserCalculatedLocation]):
        """Pull profile locations, check them against the flag."""

        profile_locations = [
            location_datum
            for location_datum in location_data
            if location_datum.lookup_type == GEOLOCATION_TYPE_PROFILE
        ]

        decisions = [(pd.country_code == self.country_code) for pd in profile_locations]

        return any(decisions)

    class Meta:
        """Set the model as a proxy."""

        proxy = True


class ProfileMatchAllLocationFlag(LocationFlag):
    """
    Implements the rules for profile-only flags.

    Rule:
        - Types: Profile (LegalAddress) only
        - Matches: All
        - Default: Flag Not Set

        For only the location data derived from the user's profile, set the flag
        if all locations match the flag location. The flag is not set if there
        are no matches, no locations, or if any individual location doesn't match.

    This is more of an example case - there's only ever one LegalAddress, so this
    and ProfileMatchAnyLocationFlag are basically the same result (right now).
    """

    def is_applicable(self, location_data: list[UserCalculatedLocation]):
        """Pull profile locations, check them against the flag."""

        profile_locations = [
            location_datum
            for location_datum in location_data
            if location_datum.lookup_type == GEOLOCATION_TYPE_PROFILE
        ]

        decisions = [(pd.country_code == self.country_code) for pd in profile_locations]

        return bool(decisions) and all(decisions)

    class Meta:
        """Set the model as a proxy."""

        proxy = True


class GeoIPMatchAnyLocationFlag(LocationFlag):
    """
    Implements the rules for GeoIP-only flags.

    Rule:
        - Types: GeoIP only
        - Matches: Any
        - Default: Flag Not Set

        For only the location data derived from the user's IP address (looked up
        via MaxMind GeoIP databases), set the flag if any locations match the flag location. The flag is not set if there are no matches or no locations.

    In practice, this should only ever consider a single location, because a user
    only connects via a single IP transport, at least as far as the request calling
    this is concerned. (For this reason there is no "all" rule.)
    """

    def is_applicable(self, location_data: list[UserCalculatedLocation]):
        """Pull GeoIP locations, check them against the flag."""

        geoip_locations = [
            location_datum
            for location_datum in location_data
            if location_datum.lookup_type == GEOLOCATION_TYPE_GEOIP
        ]

        decisions = [
            (gips.country_code == self.country_code) for gips in geoip_locations
        ]

        return any(decisions)

    class Meta:
        """Set the model as a proxy."""

        proxy = True


class ProfileAndGeoIPMatchAnyLocationFlag(LocationFlag):
    """
    Implements the rules for profile-and-GeoIP flags.

    Rule:
        - Types: Profile location and GeoIP
        - Matches: Any
        - Default: Flag Not Set

        For the location data derived from the user's IP address (looked up
        via MaxMind GeoIP databases) and from the user's profile (LegalAddress),
        set the flag if any locations match the flag location. The flag is not
        set if there are no matches or no locations.
    """

    def is_applicable(self, location_data: list[UserCalculatedLocation]):
        """Set the flag if the location matches any profile or GeoIP."""

        loc_types = (
            GEOLOCATION_TYPE_GEOIP,
            GEOLOCATION_TYPE_PROFILE,
        )

        applicable_locations = [
            location_datum
            for location_datum in location_data
            if location_datum.lookup_type in loc_types
        ]

        decisions = [
            (al.country_code == self.country_code) for al in applicable_locations
        ]

        return any(decisions)

    class Meta:
        """Set the model as a proxy."""

        proxy = True


class ProfileAndGeoIPMatchAllLocationFlag(LocationFlag):
    """
    Implements the rules for profile-and-GeoIP flags.

    Rule:
        - Types: Profile location and GeoIP
        - Matches: All
        - Default: Flag Not Set

        For the location data derived from the user's IP address (looked up
        via MaxMind GeoIP databases) and from the user's profile (LegalAddress),
        set the flag if all locations match the flag location. The flag is not
        set if there are no location data or if any location doesn't match.

    This checks for any combination of Profile and GeoIP. If there's just one,
    that's fine - we can match with that. RequireProfileGeoIPMatchAllLocationFlag
    **requires** there be a profile _and_ a GeoIP, if you want one that is more
    restrictive.
    """

    def is_applicable(self, location_data: list[UserCalculatedLocation]):
        """Set the flag if all profile and GeoIP locations match."""

        loc_types = (
            GEOLOCATION_TYPE_GEOIP,
            GEOLOCATION_TYPE_PROFILE,
        )

        applicable_locations = [
            location_datum
            for location_datum in location_data
            if location_datum.lookup_type in loc_types
        ]

        decisions = [
            (al.country_code == self.country_code) for al in applicable_locations
        ]

        return bool(decisions) and all(decisions)

    class Meta:
        """Set the model as a proxy."""

        proxy = True


class AnyTypeMatchAnyLocationFlag(LocationFlag):
    """
    Implements the rules for any location type flags.

    Rule:
        - Types: Any
        - Matches: Any
        - Default: Flag Not Set

        For **any** location data passed in, test against the flag location and
        set the flag if any match. The flag is not set if there are no locations
        or no matches.

    This is a more generic flag - it does not care how the location was derived.
    """

    def is_applicable(self, location_data: list[UserCalculatedLocation]):
        """Set the flag if any location matches, regardless of source."""

        decisions = [(ld.country_code == self.country_code) for ld in location_data]

        return any(decisions)

    class Meta:
        """Set the model as a proxy."""

        proxy = True


class AnyTypeMatchAllLocationFlag(LocationFlag):
    """
    Implements the rules for any location type flags.

    Rule:
        - Types: Any
        - Matches: All
        - Default: Flag Not Set

        For **any** location data passed in, test against the flag location and
        set the flag if all match. The flag is not set if there are no locations
        or if any location does not match.

    This is a more generic flag - it does not care how the location was derived.
    """

    def is_applicable(self, location_data: list[UserCalculatedLocation]):
        """Set the flag if all locations match, regardless of source."""

        decisions = [(ld.country_code == self.country_code) for ld in location_data]

        return bool(decisions) and all(decisions)

    class Meta:
        """Set the model as a proxy."""

        proxy = True


class RequireProfileGeoIPMatchAllLocationFlag(LocationFlag):
    """
    Implements the rules for profile and GeoIP required type flags.

    Rule:
        - Types: Profile, GeoIP
        - Matches: All
        - Default: Flag Not Set

        Set the flag if a profile and GeoIP location are present, and if all match
        the flag location. The flag is not set if locations of the required types
        aren't present, or if any of them don't match, or if there is no location
        data at all.
    """

    def is_applicable(self, location_data: list[UserCalculatedLocation]):
        """Check for a geoIP and profile location, then check their locations."""

        geoip_locations = [
            location_datum
            for location_datum in location_data
            if location_datum.lookup_type == GEOLOCATION_TYPE_GEOIP
        ]
        profile_locations = [
            location_datum
            for location_datum in location_data
            if location_datum.lookup_type == GEOLOCATION_TYPE_PROFILE
        ]

        # Short circuit - if we don't have either of these, we don't set the flag.
        if len(geoip_locations) == 0 or len(profile_locations) == 0:
            return False

        match_geoips = [
            ld_match
            for ld_match in geoip_locations
            if ld_match.country_code == self.country_code
        ]
        match_profiles = [
            ld_match
            for ld_match in profile_locations
            if ld_match.country_code == self.country_code
        ]

        return len(geoip_locations) == len(match_geoips) and len(
            profile_locations
        ) == len(match_profiles)

    class Meta:
        """Set the model as a proxy."""

        proxy = True
