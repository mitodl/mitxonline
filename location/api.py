"""API functions for locating the user."""

from django.conf import settings
from django.db.models import Q
from ipware import get_client_ip
from mitol.geoip.api import ip_to_country_code

from location.constants import (
    GEOLOCATION_TYPE_GEOIP,
    GEOLOCATION_TYPE_PROFILE,
    LOCATION_FLAG_TYPE_BLOCKED,
    LOCATION_FLAG_TYPES,
)
from location.dataclasses import UserCalculatedLocation


def get_flagged_countries(flag_type, product=None):
    """
    Return the list of flagged countries.

    A country can be flagged for a particular item; passing that in as a Product
    will return globally-flagged countries and any that are flagged for that
    Product. (This only applies to blocks for now.)

    Args:
    - flag_type (string): one of LOCATION_FLAG_TYPES
    - product (Product): a product to also consider
    Returns:
    - list of string: country codes that are blocked
    """

    if flag_type not in LOCATION_FLAG_TYPES:
        errmsg = "Invalid flag type %s"
        raise ValueError(errmsg, flag_type)

    qset = None

    if flag_type == LOCATION_FLAG_TYPE_BLOCKED:
        qset = BlockedCountry.objects

        if product:
            qset = qset.filter(Q(product__isnull=True) | Q(product=product))
        else:
            qset = qset.filter(product__isnull=True)

    elif flag_type == FLAGGED_COUNTRY_TAX:
        qset = TaxRate.objects

    return qset.values_list("country_code", flat=True).all() if qset else []


def determine_user_location(request) -> list[UserCalculatedLocation]:
    """
    Determine where the user is, using all potential lookup types.

    Currently, we determine location by either looking at the user's self-reported
    country in their profile, or by using the MaxMind GeoIP database. The
    UserCalculatedLocation dataclass returns the location data we discovered, if
    any. This doesn't set flags; the determine_user_flags function below does that.

    Because this needs an IP to look up, it requires a request object.

    Overrides:
    - MITOL_FORCE_COUNTRY - if set, force _all_ lookups to a specific country code
    - MITOL_FORCE_COUNTRY_PROFILE - if set, force _all_ lookups to use the user profile
      This also means that only the "profile" lookup type is returned.

    If both are set, MITOL_FORCE_COUNTRY takes precedence.

    Args:
    - request (HTTPRequest): the request to look up
    Returns:
    - UserCalculatedLocation: the location data for the user, if any
    """

    calculated_locations = []

    if settings.MITOL_FORCE_COUNTRY:
        # Return one each for each type of determination so flags that require
        # one or the other (or both) are set appropriately.
        return [
            UserCalculatedLocation(
                country_code=settings.MITOL_FORCE_COUNTRY,
                lookup_type=GEOLOCATION_TYPE_PROFILE,
                ip="0.0.0.0",
            ),
            UserCalculatedLocation(
                country_code=settings.MITOL_FORCE_COUNTRY,
                lookup_type=GEOLOCATION_TYPE_GEOIP,
                ip="0.0.0.0",
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
                ip="0.0.0.0",
            )
        )

    if settings.MITOL_UE_FORCE_PROFILE_COUNTRY:
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


def determine_user_flags(request, flag_type):
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



    If MITOL_UE_FORCE_PROFILE_COUNTRY is set, then this will _always_ return the
    country code listed in the profile.

    Args:
    - request (Request): the current request
    - flagged_countries (None or list): a list of flagged countries

    Returns:
    - UserCalculatedLocation:
        ISO country code (ISO 3166 alpha2) and one of the GEOLOCATION_TYPE constants
    """

    user_locations = determine_user_location(request)

    if len(user_locations) == 0:
        return

    # Now pull the flags for the type and then determine if they should be set.
    # Tomorrow probably though.
