"""API functions for locating the user."""

from django.conf import settings
from ipware import get_client_ip
from mitol.geoip.api import ip_to_country_code

from location.constants import (
    GEOLOCATION_TYPE_GEOIP,
    GEOLOCATION_TYPE_PROFILE,
    LOCATION_FLAG_TYPES,
)
from location.dataclasses import UserCalculatedLocation
from location.models import LocationFlag


def determine_user_location(request) -> list[UserCalculatedLocation]:
    """
    Determine where the user is, using all potential lookup types.

    Currently, we determine location by either looking at the user's self-reported
    country in their profile, or by using the MaxMind GeoIP database. The
    UserCalculatedLocation dataclass returns the location data we discovered, if
    any. This doesn't set flags; the determine_user_flags function below does that.

    Because this needs an IP to look up, it requires a request object.

    Overrides:
    - LOCATION_FORCE_COUNTRY - if set, force _all_ lookups to a specific country code
    - LOCATION_FORCE_COUNTRY_PROFILE - if set, force _all_ lookups to use the user profile
      This also means that only the "profile" lookup type is returned.

    If both are set, LOCATION_FORCE_COUNTRY takes precedence.

    Args:
    - request (HTTPRequest): the request to look up
    Returns:
    - UserCalculatedLocation: the location data for the user, if any
    """

    calculated_locations = []

    if settings.LOCATION_FORCE_COUNTRY:
        # Return one each for each type of determination so flags that require
        # one or the other (or both) are set appropriately.
        return [
            UserCalculatedLocation(
                country_code=settings.LOCATION_FORCE_COUNTRY,
                lookup_type=GEOLOCATION_TYPE_PROFILE,
                ip="",
            ),
            UserCalculatedLocation(
                country_code=settings.LOCATION_FORCE_COUNTRY,
                lookup_type=GEOLOCATION_TYPE_GEOIP,
                ip="0.0.0.0",  # noqa: S104
            ),
        ]

    profile_code = (
        request.user.legal_address.country_code
        if request.user.is_authenticated and request.user.legal_address
        else None
    )

    if profile_code:
        calculated_locations.append(
            UserCalculatedLocation(
                country_code=profile_code,
                lookup_type=GEOLOCATION_TYPE_PROFILE,
                ip="",
            )
        )

    if settings.LOCATION_FORCE_PROFILE_COUNTRY:
        return calculated_locations

    user_ip, _ = get_client_ip(request)
    geoip_code = ip_to_country_code(user_ip)

    calculated_locations.append(
        UserCalculatedLocation(
            country_code=geoip_code,
            lookup_type=GEOLOCATION_TYPE_GEOIP,
            ip=user_ip,
        )
    )

    return calculated_locations


def determine_user_flags(request, *, flag_type=None):
    """
    Determine where the user is, based on various details.

    We can determine the user's location by using different sources:
    - We can look their IP address up via the MaxMind GeoIP database
    - Their profile can contain a country code

    If a LocationFlag exists that matches any of the user's potential locations,
    we then make the determination to set the flag based on the rule.

    These rules are defined in constants.py and include a few different
    scenarios, such as:
    - The flag is set if the user's profile matches.
    - The flag is set if the user's profile matches _and_ the GeoIP location matches.
    - The flag is set if the user's GeoIP matches _or_ the profile matches.

    If there are flags that should be set, the LocationFlag objects that matched
    will be returned.

    Args:
    - request (Request): the current request
    - flag_type (None or list): a list of flagged countries

    Returns:
    - list[LocationFlag]: The matching flags
    """

    if flag_type and flag_type not in LOCATION_FLAG_TYPES:
        msg = f"Invalid flag type {flag_type}"
        raise ValueError(msg)

    user_locations = determine_user_location(request)

    if len(user_locations) == 0:
        return []

    country_codes = [ul.country_code for ul in user_locations]

    potential_flags = LocationFlag.objects.filter(country_code__in=country_codes)

    if flag_type:
        potential_flags = potential_flags.filter(flag_type=flag_type)

    return [flag for flag in potential_flags if flag.evaluate(user_locations)]
