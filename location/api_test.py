"""Tests for the location API."""

import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory

from location.api import determine_user_flags, determine_user_location
from location.constants import (
    GEOLOCATION_TYPE_GEOIP,
    GEOLOCATION_TYPE_PROFILE,
    LOCATION_FLAG_RULE_ONLY_GEOIP,
    LOCATION_FLAG_RULE_ONLY_PROFILE,
    LOCATION_FLAG_RULE_REQUIRE_ANY,
    LOCATION_FLAG_TYPE_BLOCKED,
    LOCATION_FLAG_TYPE_TAX,
)
from location.dataclasses import UserCalculatedLocation
from location.factories import LocationFlagFactory
from users.factories import UserFactory

pytestmark = pytest.mark.django_db

USER_IP = "8.8.8.8"


@pytest.fixture(autouse=True)
def location_settings(settings):
    """Reset the location override settings."""

    settings.LOCATION_FORCE_COUNTRY = False
    settings.LOCATION_FORCE_PROFILE_COUNTRY = False


@pytest.fixture
def mock_geoip(mocker):
    """Mock the GeoIP lookup."""

    return mocker.patch("location.api.ip_to_country_code", return_value="CA")


def _make_request(user=None):
    """Make a request for the given user (or an anonymous user)."""

    request = RequestFactory().get("/", REMOTE_ADDR=USER_IP)
    request.user = user if user else AnonymousUser()
    return request


def _make_user(country):
    """Make a user with a legal address in the given country."""

    user = UserFactory.create()
    user.legal_address.country = country
    user.legal_address.save()
    return user


def test_determine_user_location(mock_geoip):
    """Location should come from both the profile and GeoIP."""

    request = _make_request(_make_user("US"))

    assert determine_user_location(request) == [
        UserCalculatedLocation(
            country_code="US", lookup_type=GEOLOCATION_TYPE_PROFILE, ip=""
        ),
        UserCalculatedLocation(
            country_code="CA", lookup_type=GEOLOCATION_TYPE_GEOIP, ip=USER_IP
        ),
    ]
    mock_geoip.assert_called_once_with(USER_IP)


def test_determine_user_location_anonymous(mock_geoip):
    """Anonymous users should only get a GeoIP location."""

    assert determine_user_location(_make_request()) == [
        UserCalculatedLocation(
            country_code="CA", lookup_type=GEOLOCATION_TYPE_GEOIP, ip=USER_IP
        ),
    ]


def test_determine_user_location_no_legal_address(mock_geoip):
    """Users without a legal address should only get a GeoIP location."""

    user = UserFactory.create(legal_address=None)

    assert determine_user_location(_make_request(user)) == [
        UserCalculatedLocation(
            country_code="CA", lookup_type=GEOLOCATION_TYPE_GEOIP, ip=USER_IP
        ),
    ]


def test_determine_user_location_blank_country(mock_geoip):
    """Users without a country in their legal address should only get a GeoIP location."""

    request = _make_request(_make_user(""))

    assert determine_user_location(request) == [
        UserCalculatedLocation(
            country_code="CA", lookup_type=GEOLOCATION_TYPE_GEOIP, ip=USER_IP
        ),
    ]


@pytest.mark.parametrize("force_profile", [True, False])
@pytest.mark.parametrize("authenticated", [True, False])
def test_determine_user_location_force_country(
    settings, mock_geoip, force_profile, authenticated
):
    """LOCATION_FORCE_COUNTRY should override everything else."""

    settings.LOCATION_FORCE_COUNTRY = "FR"
    settings.LOCATION_FORCE_PROFILE_COUNTRY = force_profile
    request = _make_request(_make_user("US") if authenticated else None)

    assert determine_user_location(request) == [
        UserCalculatedLocation(
            country_code="FR", lookup_type=GEOLOCATION_TYPE_PROFILE, ip=""
        ),
        UserCalculatedLocation(
            country_code="FR",
            lookup_type=GEOLOCATION_TYPE_GEOIP,
            ip="0.0.0.0",  # noqa: S104
        ),
    ]
    mock_geoip.assert_not_called()


@pytest.mark.parametrize("authenticated", [True, False])
def test_determine_user_location_force_profile(settings, mock_geoip, authenticated):
    """LOCATION_FORCE_PROFILE_COUNTRY should skip the GeoIP lookup."""

    settings.LOCATION_FORCE_PROFILE_COUNTRY = True
    request = _make_request(_make_user("US") if authenticated else None)

    expected = (
        [
            UserCalculatedLocation(
                country_code="US", lookup_type=GEOLOCATION_TYPE_PROFILE, ip=""
            )
        ]
        if authenticated
        else []
    )

    assert determine_user_location(request) == expected
    mock_geoip.assert_not_called()


def test_determine_user_flags_invalid_flag_type():
    """An invalid flag type should raise a ValueError."""

    with pytest.raises(ValueError, match="Invalid flag type"):
        determine_user_flags(_make_request(), flag_type="not-a-type")


def test_determine_user_flags_no_locations(settings, mock_geoip):
    """If we can't locate the user, no flags should be returned."""

    settings.LOCATION_FORCE_PROFILE_COUNTRY = True
    LocationFlagFactory.create(
        country_code="US", determination_rule=LOCATION_FLAG_RULE_REQUIRE_ANY
    )

    assert determine_user_flags(_make_request()) == []


def test_determine_user_flags(mock_geoip):
    """Only flags that match the user's location and pass their rule should be returned."""

    request = _make_request(_make_user("US"))

    profile_flag = LocationFlagFactory.create(
        country_code="US", determination_rule=LOCATION_FLAG_RULE_ONLY_PROFILE
    )
    geoip_flag = LocationFlagFactory.create(
        country_code="CA", determination_rule=LOCATION_FLAG_RULE_ONLY_GEOIP
    )
    # Matches the country, but the rule doesn't pass
    LocationFlagFactory.create(
        country_code="US", determination_rule=LOCATION_FLAG_RULE_ONLY_GEOIP
    )
    # Doesn't match the country
    LocationFlagFactory.create(
        country_code="FR", determination_rule=LOCATION_FLAG_RULE_REQUIRE_ANY
    )
    # Inactive
    LocationFlagFactory.create(
        country_code="US",
        determination_rule=LOCATION_FLAG_RULE_REQUIRE_ANY,
        is_active=False,
    )

    assert {flag.pk for flag in determine_user_flags(request)} == {
        profile_flag.pk,
        geoip_flag.pk,
    }


@pytest.mark.parametrize(
    "flag_type", [LOCATION_FLAG_TYPE_TAX, LOCATION_FLAG_TYPE_BLOCKED]
)
def test_determine_user_flags_flag_type(settings, flag_type):
    """Specifying a flag type should only return flags of that type."""

    settings.LOCATION_FORCE_COUNTRY = "US"
    flags = {
        type_: LocationFlagFactory.create(
            country_code="US",
            determination_rule=LOCATION_FLAG_RULE_REQUIRE_ANY,
            flag_type=type_,
        )
        for type_ in (LOCATION_FLAG_TYPE_TAX, LOCATION_FLAG_TYPE_BLOCKED)
    }

    assert [
        flag.pk for flag in determine_user_flags(_make_request(), flag_type=flag_type)
    ] == [flags[flag_type].pk]
