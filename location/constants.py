"""Constants for location."""

from location.dataclasses import LocationFlagRule

# Geolocation mechanisms

GEOLOCATION_TYPE_PROFILE = "profile"
GEOLOCATION_TYPE_GEOIP = "geoip"
GEOLOCATION_TYPE_NONE = "none"
GEOLOCATION_TYPE_CHOICES = [
    (GEOLOCATION_TYPE_PROFILE, "Profile"),
    (GEOLOCATION_TYPE_GEOIP, "GeoIP"),
    (GEOLOCATION_TYPE_NONE, "None"),
]

# Flag determination rules
# These are the different ways the flag may be set for a given user. Each maps
# to a LocationFlagRule in LOCATION_FLAG_RULE_DEFINITIONS below, which
# LocationFlag.evaluate uses to decide whether the flag is set.

LOCATION_FLAG_RULE_MATCH_PROFILE_ANY = "profile-any"
LOCATION_FLAG_RULE_MATCH_PROFILE_ANY_NAME = "Check any of the user's profile locations."
LOCATION_FLAG_RULE_MATCH_PROFILE_ALL = "profile-all"
LOCATION_FLAG_RULE_MATCH_PROFILE_ALL_NAME = "Check all of the user's profile locations."
LOCATION_FLAG_RULE_MATCH_GEOIP_ANY = "geoip-any"
LOCATION_FLAG_RULE_MATCH_GEOIP_ANY_NAME = "Check any of the user's GeoIP locations."
LOCATION_FLAG_RULE_MATCH_PROFILE_GEOIP_ANY = "profile-geoip-any"
LOCATION_FLAG_RULE_MATCH_PROFILE_GEOIP_ANY_NAME = (
    "Check if any profile or GeoIP location match."
)
LOCATION_FLAG_RULE_MATCH_PROFILE_GEOIP_ALL = "profile-geoip-all"
LOCATION_FLAG_RULE_MATCH_PROFILE_GEOIP_ALL_NAME = (
    "Ensure all profile or GeoIP location match."
)

LOCATION_FLAG_RULE_MATCH_ANY = "any-type-any"
LOCATION_FLAG_RULE_MATCH_ANY_NAME = (
    "Check any of the derived locations for a match, regardless of source."
)
LOCATION_FLAG_RULE_MATCH_ALL = "any-type-all"
LOCATION_FLAG_RULE_MATCH_ALL_NAME = (
    "Ensure all of the derived locations match, regardless of source."
)

LOCATION_FLAG_RULE_REQUIRE_PROFILE_GEOIP_MATCH_ALL = "require-profile-geoip-all"
LOCATION_FLAG_RULE_REQUIRE_PROFILE_GEOIP_MATCH_ALL_NAME = "Require a GeoIP and a profile location exist, and check that all of them match the flag location."

LOCATION_FLAG_RULES = [
    LOCATION_FLAG_RULE_MATCH_PROFILE_ANY,
    LOCATION_FLAG_RULE_MATCH_PROFILE_ALL,
    LOCATION_FLAG_RULE_MATCH_GEOIP_ANY,
    LOCATION_FLAG_RULE_MATCH_PROFILE_GEOIP_ANY,
    LOCATION_FLAG_RULE_MATCH_PROFILE_GEOIP_ALL,
    LOCATION_FLAG_RULE_MATCH_ANY,
    LOCATION_FLAG_RULE_MATCH_ALL,
    LOCATION_FLAG_RULE_REQUIRE_PROFILE_GEOIP_MATCH_ALL,
]
LOCATION_FLAG_RULES_NAMES = [
    LOCATION_FLAG_RULE_MATCH_PROFILE_ANY_NAME,
    LOCATION_FLAG_RULE_MATCH_PROFILE_ALL_NAME,
    LOCATION_FLAG_RULE_MATCH_GEOIP_ANY_NAME,
    LOCATION_FLAG_RULE_MATCH_PROFILE_GEOIP_ANY_NAME,
    LOCATION_FLAG_RULE_MATCH_PROFILE_GEOIP_ALL_NAME,
    LOCATION_FLAG_RULE_MATCH_ANY_NAME,
    LOCATION_FLAG_RULE_MATCH_ALL_NAME,
    LOCATION_FLAG_RULE_REQUIRE_PROFILE_GEOIP_MATCH_ALL_NAME,
]
LOCATION_FLAG_RULE_CHOICES = list(zip(LOCATION_FLAG_RULES, LOCATION_FLAG_RULES_NAMES))

# Flagged countries constants
# We can flag a country for tax assessment, or for access control.

LOCATION_FLAG_TYPE_TAX = "tax"
LOCATION_FLAG_TYPE_BLOCKED = "blocked"
LOCATION_FLAG_TYPES = [
    LOCATION_FLAG_TYPE_TAX,
    LOCATION_FLAG_TYPE_BLOCKED,
]
LOCATION_FLAG_TYPE_CHOICES = list(zip(LOCATION_FLAG_TYPES, LOCATION_FLAG_TYPES))

# How each rule is evaluated:
# - lookup_types: the location types the rule considers (None means all types)
# - match_all: whether all considered locations must match (vs. any of them)
# - require_all_types: whether each of lookup_types must have at least one location
# A rule never sets the flag if there are no locations to consider.

_PROFILE_ONLY = frozenset({GEOLOCATION_TYPE_PROFILE})
_GEOIP_ONLY = frozenset({GEOLOCATION_TYPE_GEOIP})
_PROFILE_AND_GEOIP = frozenset({GEOLOCATION_TYPE_PROFILE, GEOLOCATION_TYPE_GEOIP})

LOCATION_FLAG_RULE_DEFINITIONS = {
    LOCATION_FLAG_RULE_MATCH_PROFILE_ANY: LocationFlagRule(
        lookup_types=_PROFILE_ONLY, match_all=False
    ),
    LOCATION_FLAG_RULE_MATCH_PROFILE_ALL: LocationFlagRule(
        lookup_types=_PROFILE_ONLY, match_all=True
    ),
    LOCATION_FLAG_RULE_MATCH_GEOIP_ANY: LocationFlagRule(
        lookup_types=_GEOIP_ONLY, match_all=False
    ),
    LOCATION_FLAG_RULE_MATCH_PROFILE_GEOIP_ANY: LocationFlagRule(
        lookup_types=_PROFILE_AND_GEOIP, match_all=False
    ),
    LOCATION_FLAG_RULE_MATCH_PROFILE_GEOIP_ALL: LocationFlagRule(
        lookup_types=_PROFILE_AND_GEOIP, match_all=True
    ),
    LOCATION_FLAG_RULE_MATCH_ANY: LocationFlagRule(lookup_types=None, match_all=False),
    LOCATION_FLAG_RULE_MATCH_ALL: LocationFlagRule(lookup_types=None, match_all=True),
    LOCATION_FLAG_RULE_REQUIRE_PROFILE_GEOIP_MATCH_ALL: LocationFlagRule(
        lookup_types=_PROFILE_AND_GEOIP, match_all=True, require_all_types=True
    ),
}
