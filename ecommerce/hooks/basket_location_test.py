"""Tests for the basket location hook."""

import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory

from ecommerce.constants import BASKET_UPDATE_ADD_ITEM
from ecommerce.dataclasses import BasketUpdate
from ecommerce.factories import BasketFactory, ProductFactory
from ecommerce.hooks.basket_location import BasketLocation
from location.constants import (
    GEOLOCATION_TYPE_GEOIP,
    GEOLOCATION_TYPE_NONE,
    GEOLOCATION_TYPE_PROFILE,
)
from location.dataclasses import UserCalculatedLocation

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    ("locations", "expected_country", "expected_source"),
    [
        (
            [
                UserCalculatedLocation("US", GEOLOCATION_TYPE_PROFILE, ""),
                UserCalculatedLocation("IN", GEOLOCATION_TYPE_GEOIP, "1.2.3.4"),
            ],
            "IN",
            GEOLOCATION_TYPE_GEOIP,
        ),
        (
            [UserCalculatedLocation("US", GEOLOCATION_TYPE_PROFILE, "")],
            "US",
            GEOLOCATION_TYPE_PROFILE,
        ),
        ([], "", GEOLOCATION_TYPE_NONE),
    ],
)
def test_basket_location_hook(
    mocker, user, locations, expected_country, expected_source
):
    """The hook geolocates the user and saves the result to the basket."""

    mock_locate = mocker.patch(
        "location.api.determine_user_location", return_value=locations
    )
    basket = BasketFactory.create(user=user)
    request = RequestFactory().get("/")
    request.user = user

    BasketLocation().basket_pre_update(
        request=request,
        basket=basket,
        update=BasketUpdate(
            operation=BASKET_UPDATE_ADD_ITEM, product=ProductFactory.create()
        ),
    )

    mock_locate.assert_called_once_with(request)
    basket.refresh_from_db()
    assert basket.location_country_code == expected_country
    assert basket.location_source == expected_source
    assert basket.user_locations == locations
    assert basket.location_determined_on is not None


def test_basket_location_hook_anonymous(settings):
    """An anonymous basket is located too (by GeoIP, as there's no profile)."""

    settings.LOCATION_FORCE_COUNTRY = "in"
    basket = BasketFactory.create(
        user=None, anonymous_id="8c1a3b2e-1d4f-4c55-9f6b-2a7e0b1c9d01"
    )
    request = RequestFactory().get("/")
    request.user = AnonymousUser()

    BasketLocation().basket_pre_update(
        request=request,
        basket=basket,
        update=BasketUpdate(operation=BASKET_UPDATE_ADD_ITEM),
    )

    basket.refresh_from_db()
    assert basket.location_country_code == "IN"
    assert basket.location_source == GEOLOCATION_TYPE_GEOIP
