"""Constants for location."""

# Geolocation mechanisms

GEOLOCATION_TYPE_PROFILE = "profile"
GEOLOCATION_TYPE_GEOIP = "geoip"
GEOLOCATION_TYPE_NONE = "none"
GEOLOCATION_TYPES = [
    GEOLOCATION_TYPE_PROFILE,
    GEOLOCATION_TYPE_GEOIP,
    GEOLOCATION_TYPE_NONE,
]
GEOLOCATION_CHOICES = zip(GEOLOCATION_TYPES, GEOLOCATION_TYPES)

# Flag determination rules
# These set how to determine the user's location when checking for a location
# flag. For example, if there's a flag for tax for "Country X" and the flag is
# set to use "only-profile", the flag only counts if the user's profile states
# that they're in "Country X", even if we can tell that the user's physically in
# "Country X" via GeoIP.

LOCATION_FLAG_RULE_ONLY_PROFILE = "only-profile"
LOCATION_FLAG_RULE_ONLY_PROFILE_NAME = "Only match on the user's profile location."
LOCATION_FLAG_RULE_ONLY_GEOIP = "only-geoip"
LOCATION_FLAG_RULE_ONLY_GEOIP_NAME = "Only match on the user's GeoIP location."
LOCATION_FLAG_RULE_REQUIRE_PROFILE_GEOIP = "require-profile-geoip"
LOCATION_FLAG_RULE_REQUIRE_PROFILE_GEOIP_NAME = (
    "Only match if the location matches both profile and GeoIP."
)
LOCATION_FLAG_RULE_REQUIRE_ANY = "require-any"
LOCATION_FLAG_RULE_REQUIRE_ANY_NAME = "Match if any lookup is successful."

LOCATION_FLAG_RULES = [
    LOCATION_FLAG_RULE_ONLY_PROFILE,
    LOCATION_FLAG_RULE_ONLY_GEOIP,
    LOCATION_FLAG_RULE_REQUIRE_PROFILE_GEOIP,
    LOCATION_FLAG_RULE_REQUIRE_ANY,
]
LOCATION_FLAG_RULES_NAMES = [
    LOCATION_FLAG_RULE_ONLY_PROFILE_NAME,
    LOCATION_FLAG_RULE_ONLY_GEOIP_NAME,
    LOCATION_FLAG_RULE_REQUIRE_PROFILE_GEOIP_NAME,
    LOCATION_FLAG_RULE_REQUIRE_ANY_NAME,
]
LOCATION_FLAG_RULE_CHOICES = zip(LOCATION_FLAG_RULES, LOCATION_FLAG_RULES_NAMES)

# Flagged countries constants
# We can flag a country for tax assessment, or for access control.

LOCATION_FLAG_TYPE_TAX = "tax"
LOCATION_FLAG_TYPE_BLOCKED = "blocked"
LOCATION_FLAG_TYPES = [
    LOCATION_FLAG_TYPE_TAX,
    LOCATION_FLAG_TYPE_BLOCKED,
]
LOCATION_FLAG_TYPE_CHOICES = zip(LOCATION_FLAG_TYPES, LOCATION_FLAG_TYPES)
