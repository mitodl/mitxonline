"""Tests for location models."""

import pytest

from location.constants import (
    GEOLOCATION_TYPE_GEOIP,
    GEOLOCATION_TYPE_NONE,
    GEOLOCATION_TYPE_PROFILE,
    LOCATION_FLAG_RULE_MATCH_ALL,
    LOCATION_FLAG_RULE_MATCH_ANY,
    LOCATION_FLAG_RULE_MATCH_GEOIP_ANY,
    LOCATION_FLAG_RULE_MATCH_PROFILE_ALL,
    LOCATION_FLAG_RULE_MATCH_PROFILE_ANY,
    LOCATION_FLAG_RULE_MATCH_PROFILE_GEOIP_ALL,
    LOCATION_FLAG_RULE_MATCH_PROFILE_GEOIP_ANY,
    LOCATION_FLAG_RULE_REQUIRE_PROFILE_GEOIP_MATCH_ALL,
    LOCATION_FLAG_RULES,
)
from location.dataclasses import UserCalculatedLocation
from location.factories import LocationFlagFactory
from location.models import (
    AnyTypeMatchAllLocationFlag,
    AnyTypeMatchAnyLocationFlag,
    GeoIPMatchAnyLocationFlag,
    LocationFlag,
    ProfileAndGeoIPMatchAllLocationFlag,
    ProfileAndGeoIPMatchAnyLocationFlag,
    ProfileMatchAllLocationFlag,
    ProfileMatchAnyLocationFlag,
    RequireProfileGeoIPMatchAllLocationFlag,
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


def _other_type(country_code):
    """Make a location that is neither profile- nor GeoIP-based."""
    return UserCalculatedLocation(
        country_code=country_code, lookup_type=GEOLOCATION_TYPE_NONE, ip=""
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
    # Multiple locations of a single type - separates the "any" and "all" rules
    "profile-match-profile-other": [_profile(FLAG_COUNTRY), _profile(OTHER_COUNTRY)],
    "geoip-match-geoip-other": [_geoip(FLAG_COUNTRY), _geoip(OTHER_COUNTRY)],
    # Locations of another type - separates profile+GeoIP from any-type rules
    "profile-match-othertype-other": [
        _profile(FLAG_COUNTRY),
        _other_type(OTHER_COUNTRY),
    ],
    "othertype-match-only": [_other_type(FLAG_COUNTRY)],
    "profile-match-geoip-match-othertype-other": [
        _profile(FLAG_COUNTRY),
        _geoip(FLAG_COUNTRY),
        _other_type(OTHER_COUNTRY),
    ],
}

# The scenarios above in which each rule should set the flag. The flag should
# not be set for any scenario not listed for a rule.
RULE_EXPECTATIONS = {
    LOCATION_FLAG_RULE_MATCH_PROFILE_ANY: {
        "profile-match-geoip-match",
        "profile-match-geoip-other",
        "profile-match-only",
        "profile-match-geoip-unknown",
        "profile-match-profile-other",
        "profile-match-othertype-other",
        "profile-match-geoip-match-othertype-other",
    },
    LOCATION_FLAG_RULE_MATCH_PROFILE_ALL: {
        "profile-match-geoip-match",
        "profile-match-geoip-other",
        "profile-match-only",
        "profile-match-geoip-unknown",
        "profile-match-othertype-other",
        "profile-match-geoip-match-othertype-other",
    },
    LOCATION_FLAG_RULE_MATCH_GEOIP_ANY: {
        "profile-match-geoip-match",
        "profile-other-geoip-match",
        "geoip-match-only",
        "geoip-match-geoip-other",
        "profile-match-geoip-match-othertype-other",
    },
    LOCATION_FLAG_RULE_MATCH_PROFILE_GEOIP_ANY: {
        "profile-match-geoip-match",
        "profile-match-geoip-other",
        "profile-other-geoip-match",
        "profile-match-only",
        "geoip-match-only",
        "profile-match-geoip-unknown",
        "profile-match-profile-other",
        "geoip-match-geoip-other",
        "profile-match-othertype-other",
        "profile-match-geoip-match-othertype-other",
    },
    LOCATION_FLAG_RULE_MATCH_PROFILE_GEOIP_ALL: {
        "profile-match-geoip-match",
        "profile-match-only",
        "geoip-match-only",
        "profile-match-othertype-other",
        "profile-match-geoip-match-othertype-other",
    },
    LOCATION_FLAG_RULE_MATCH_ANY: {
        "profile-match-geoip-match",
        "profile-match-geoip-other",
        "profile-other-geoip-match",
        "profile-match-only",
        "geoip-match-only",
        "profile-match-geoip-unknown",
        "profile-match-profile-other",
        "geoip-match-geoip-other",
        "profile-match-othertype-other",
        "othertype-match-only",
        "profile-match-geoip-match-othertype-other",
    },
    LOCATION_FLAG_RULE_MATCH_ALL: {
        "profile-match-geoip-match",
        "profile-match-only",
        "geoip-match-only",
        "othertype-match-only",
    },
    LOCATION_FLAG_RULE_REQUIRE_PROFILE_GEOIP_MATCH_ALL: {
        "profile-match-geoip-match",
        "profile-match-geoip-match-othertype-other",
    },
}

RULE_MODELS = {
    LOCATION_FLAG_RULE_MATCH_PROFILE_ANY: ProfileMatchAnyLocationFlag,
    LOCATION_FLAG_RULE_MATCH_PROFILE_ALL: ProfileMatchAllLocationFlag,
    LOCATION_FLAG_RULE_MATCH_GEOIP_ANY: GeoIPMatchAnyLocationFlag,
    LOCATION_FLAG_RULE_MATCH_PROFILE_GEOIP_ANY: ProfileAndGeoIPMatchAnyLocationFlag,
    LOCATION_FLAG_RULE_MATCH_PROFILE_GEOIP_ALL: ProfileAndGeoIPMatchAllLocationFlag,
    LOCATION_FLAG_RULE_MATCH_ANY: AnyTypeMatchAnyLocationFlag,
    LOCATION_FLAG_RULE_MATCH_ALL: AnyTypeMatchAllLocationFlag,
    LOCATION_FLAG_RULE_REQUIRE_PROFILE_GEOIP_MATCH_ALL: RequireProfileGeoIPMatchAllLocationFlag,
}


def test_rule_constants_are_unique():
    """Each rule needs a distinct value, or two rules map to the same model."""

    assert len(set(LOCATION_FLAG_RULES)) == len(LOCATION_FLAG_RULES)


def test_all_rules_covered():
    """Every rule should have a rule model and test expectations."""

    assert set(RULE_MODELS) == set(LOCATION_FLAG_RULES)
    assert set(RULE_EXPECTATIONS) == set(LOCATION_FLAG_RULES)
    for expected in RULE_EXPECTATIONS.values():
        assert expected <= set(LOCATION_SCENARIOS)


def test_soft_delete():
    """Deleting a flag should deactivate it rather than remove it."""

    flag = LocationFlagFactory.create()
    flag.delete()

    flag.refresh_from_db()
    assert flag.is_active is False
    assert flag.deleted_on is not None
    assert not LocationFlag.objects.filter(pk=flag.pk).exists()
    assert LocationFlag.all_objects.filter(pk=flag.pk).exists()


@pytest.mark.parametrize("manager_name", ["objects", "all_objects"])
def test_queryset_soft_delete(manager_name):
    """Deleting through a queryset should deactivate rows rather than remove them."""

    flags = LocationFlagFactory.create_batch(2)
    manager = getattr(LocationFlag, manager_name)
    manager.filter(pk__in=[flag.pk for flag in flags]).delete()

    for flag in flags:
        flag.refresh_from_db()
        assert flag.is_active is False
        assert flag.deleted_on is not None
    assert not LocationFlag.objects.filter(pk__in=[f.pk for f in flags]).exists()


def test_evaluate_deleted_flag():
    """Evaluating a soft-deleted flag should still work via the rule model."""

    flag = LocationFlagFactory.create(
        country_code=FLAG_COUNTRY, determination_rule=LOCATION_FLAG_RULE_MATCH_ANY
    )
    flag.delete()

    assert flag.evaluate(LOCATION_SCENARIOS["profile-match-geoip-match"]) is True


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
        determination_rule=LOCATION_FLAG_RULE_MATCH_ANY,
    )

    assert flag.evaluate(LOCATION_SCENARIOS["profile-match-geoip-match"]) is False


@pytest.mark.parametrize("rule", RULE_EXPECTATIONS.keys())
@pytest.mark.parametrize("scenario", LOCATION_SCENARIOS.keys())
def test_evaluate(rule, scenario):
    """Evaluating a flag should apply the rule for its determination_rule."""

    flag = LocationFlagFactory.create(
        country_code=FLAG_COUNTRY, determination_rule=rule
    )

    assert flag.evaluate(LOCATION_SCENARIOS[scenario]) is (
        scenario in RULE_EXPECTATIONS[rule]
    )
