"""Tests for location models."""

import pytest

from location.constants import (
    GEOLOCATION_TYPE_GEOIP,
    GEOLOCATION_TYPE_PROFILE,
    LOCATION_FLAG_RULE_ONLY_GEOIP,
    LOCATION_FLAG_RULE_ONLY_PROFILE,
    LOCATION_FLAG_RULE_REQUIRE_ANY,
    LOCATION_FLAG_RULE_REQUIRE_PROFILE_GEOIP,
)
from location.dataclasses import UserCalculatedLocation
from location.factories import LocationFlagFactory
from location.models import (
    LocationFlag,
    MatchAnyLocationFlag,
    OnlyGeoIPLocationFlag,
    OnlyProfileLocationFlag,
    ProfileAndGeoIPLocationFlag,
)

pytestmark = pytest.mark.django_db

FLAG_COUNTRY = "US"
OTHER_COUNTRY = "CA"


def _profile(country_code):
    """Make a profile-based location."""
    return UserCalculatedLocation(
        country_code=country_code, lookup_type=GEOLOCATION_TYPE_PROFILE, ip=""
    )


def _geoip(country_code):
    """Make a GeoIP-based location."""
    return UserCalculatedLocation(
        country_code=country_code, lookup_type=GEOLOCATION_TYPE_GEOIP, ip="8.8.8.8"
    )


# Location data scenarios, keyed by a readable ID. The flag country is US.
LOCATION_SCENARIOS = {
    "profile-match-geoip-match": [_profile(FLAG_COUNTRY), _geoip(FLAG_COUNTRY)],
    "profile-match-geoip-other": [_profile(FLAG_COUNTRY), _geoip(OTHER_COUNTRY)],
    "profile-other-geoip-match": [_profile(OTHER_COUNTRY), _geoip(FLAG_COUNTRY)],
    "profile-other-geoip-other": [_profile(OTHER_COUNTRY), _geoip(OTHER_COUNTRY)],
    "profile-match-only": [_profile(FLAG_COUNTRY)],
    "geoip-match-only": [_geoip(FLAG_COUNTRY)],
    "profile-match-geoip-unknown": [_profile(FLAG_COUNTRY), _geoip(None)],
    "no-locations": [],
}

# Expected applicability for each rule, per scenario above.
RULE_EXPECTATIONS = {
    LOCATION_FLAG_RULE_ONLY_PROFILE: {
        "profile-match-geoip-match": True,
        "profile-match-geoip-other": True,
        "profile-other-geoip-match": False,
        "profile-other-geoip-other": False,
        "profile-match-only": True,
        "geoip-match-only": False,
        "profile-match-geoip-unknown": True,
        "no-locations": False,
    },
    LOCATION_FLAG_RULE_ONLY_GEOIP: {
        "profile-match-geoip-match": True,
        "profile-match-geoip-other": False,
        "profile-other-geoip-match": True,
        "profile-other-geoip-other": False,
        "profile-match-only": False,
        "geoip-match-only": True,
        "profile-match-geoip-unknown": False,
        "no-locations": False,
    },
    LOCATION_FLAG_RULE_REQUIRE_PROFILE_GEOIP: {
        "profile-match-geoip-match": True,
        "profile-match-geoip-other": False,
        "profile-other-geoip-match": False,
        "profile-other-geoip-other": False,
        "profile-match-only": False,
        "geoip-match-only": False,
        "profile-match-geoip-unknown": False,
        "no-locations": False,
    },
    LOCATION_FLAG_RULE_REQUIRE_ANY: {
        "profile-match-geoip-match": True,
        "profile-match-geoip-other": True,
        "profile-other-geoip-match": True,
        "profile-other-geoip-other": False,
        "profile-match-only": True,
        "geoip-match-only": True,
        "profile-match-geoip-unknown": True,
        "no-locations": False,
    },
}

RULE_MODELS = {
    LOCATION_FLAG_RULE_ONLY_PROFILE: OnlyProfileLocationFlag,
    LOCATION_FLAG_RULE_ONLY_GEOIP: OnlyGeoIPLocationFlag,
    LOCATION_FLAG_RULE_REQUIRE_PROFILE_GEOIP: ProfileAndGeoIPLocationFlag,
    LOCATION_FLAG_RULE_REQUIRE_ANY: MatchAnyLocationFlag,
}


def test_soft_delete():
    """Deleting a flag should deactivate it rather than remove it."""

    flag = LocationFlagFactory.create()
    flag.delete()

    flag.refresh_from_db()
    assert flag.is_active is False
    assert flag.deleted_on is not None
    assert not LocationFlag.objects.filter(pk=flag.pk).exists()
    assert LocationFlag.all_objects.filter(pk=flag.pk).exists()


def test_clean_sets_deleted_on():
    """Saving an inactive flag without a deleted_on date should set one."""

    # build + save rather than create: create() uses force_insert, which skips
    # full_clean() in ValidateOnSaveMixin.
    flag = LocationFlagFactory.build(is_active=False)
    flag.save()

    flag.refresh_from_db()
    assert flag.deleted_on is not None


def test_active_manager():
    """The default manager should only return active flags."""

    active = LocationFlagFactory.create()
    inactive = LocationFlagFactory.create(is_active=False)

    assert list(LocationFlag.objects.all()) == [active]
    assert set(LocationFlag.all_objects.all()) == {active, inactive}


@pytest.mark.parametrize(("rule", "rule_model"), RULE_MODELS.items())
def test_get_rule_model_for_object(rule, rule_model):
    """The rule model should be the proxy model that matches the rule."""

    flag = LocationFlagFactory.create(determination_rule=rule)
    result = LocationFlag.get_rule_model_for_object(flag)

    assert isinstance(result, rule_model)
    assert result.pk == flag.pk


def test_get_rule_model_for_object_invalid_rule():
    """A rule without a rule model should raise a ValueError."""

    flag = LocationFlag(determination_rule="not-a-rule")

    with pytest.raises(ValueError, match="not-a-rule"):
        LocationFlag.get_rule_model_for_object(flag)


def test_evaluate_unsaved():
    """An unsaved flag should never be applicable."""

    flag = LocationFlagFactory.build(
        country_code=FLAG_COUNTRY,
        determination_rule=LOCATION_FLAG_RULE_REQUIRE_ANY,
    )

    assert flag.evaluate(LOCATION_SCENARIOS["profile-match-geoip-match"]) is False


@pytest.mark.parametrize("rule", RULE_EXPECTATIONS.keys())
@pytest.mark.parametrize("scenario", LOCATION_SCENARIOS.keys())
def test_evaluate(rule, scenario):
    """Evaluating a flag should apply the rule for its determination_rule."""

    flag = LocationFlagFactory.create(
        country_code=FLAG_COUNTRY, determination_rule=rule
    )

    assert (
        flag.evaluate(LOCATION_SCENARIOS[scenario]) is RULE_EXPECTATIONS[rule][scenario]
    )
