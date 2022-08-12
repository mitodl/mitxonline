import random
from decimal import Decimal

import pytest
from django.urls import reverse

from flexiblepricing import models
from flexiblepricing.factories import (
    CountryIncomeThresholdFactory,
    CurrencyExchangeRateFactory,
    FlexiblePriceFactory,
    FlexiblePriceTierFactory,
)

pytestmark = [pytest.mark.django_db]


@pytest.fixture()
def income_threshold():
    return CountryIncomeThresholdFactory.create()


@pytest.fixture()
def exchange_rate():
    return CurrencyExchangeRateFactory.create()


@pytest.fixture()
def flexible_price_application():
    return FlexiblePriceFactory.create()


def test_basic_country_income_thresholds(user_drf_client, income_threshold):
    """
    Basic operations test for income thresholds.
    """
    resp = user_drf_client.get(reverse("fp_countryincomethresholds_api-list"))
    assert resp.status_code == 200
    assert len(resp.json()) >= 1

    random_threshold = random.randrange(2500, 180000, 2500)

    new_threshold = {"country_code": "XX", "income_threshold": random_threshold}

    resp = user_drf_client.post(
        reverse("fp_countryincomethresholds_api-list"), new_threshold
    )

    assert resp.status_code == 201
    assert len(resp.json()) >= 2
    data = resp.json()
    assert data["income_threshold"] == random_threshold

    resp = user_drf_client.get(reverse("fp_countryincomethresholds_api-list"))
    assert resp.status_code == 200
    assert len(resp.json()) >= 2


def test_basic_exchange_rates(user_drf_client, exchange_rate):
    """
    Basic operations test for exchange rates.
    """
    resp = user_drf_client.get(reverse("fp_exchangerates_api-list"))
    assert resp.status_code == 200
    assert len(resp.json()) >= 1

    random_rate = random.randrange(0, 100, 1) / 100
    new_rate = {"currency_code": "XXX", "exchange_rate": random_rate}

    resp = user_drf_client.post(reverse("fp_exchangerates_api-list"), new_rate)

    assert resp.status_code == 201
    assert len(resp.json()) >= 2
    data = resp.json()
    assert Decimal(data["exchange_rate"]).quantize(Decimal("0.001")) == Decimal(
        random_rate
    ).quantize(Decimal("0.001"))

    resp = user_drf_client.get(reverse("fp_exchangerates_api-list"))
    assert resp.status_code == 200
    assert len(resp.json()) >= 2


def test_basic_flex_payments(
    user_drf_client, admin_drf_client, user, flexible_price_application, mocker
):
    """
    Tests flexible payment applications. This clones the one that's made in the
    factory, then sets it to the user_drf_client user, then tests - the regular
    client should just see theirs and the admin one should see more than one.
    """
    mocker.patch(
        "flexiblepricing.tasks.notify_flexible_price_status_change_email.delay"
    )
    myapp = flexible_price_application
    myapp.user = user
    myapp.pk = None
    myapp.save()

    resp = user_drf_client.get(reverse("fp_flexiblepricing_api-list"))
    assert resp.status_code == 200
    json_response = resp.json()
    assert len(json_response["results"]) == 1
    assert json_response["results"][0]["user"]["id"] == user.id

    allapps = models.FlexiblePrice.objects.all()

    resp = admin_drf_client.get(reverse("fp_admin_flexiblepricing_api-list"))
    json_response = resp.json()
    assert resp.status_code == 200
    assert json_response["count"] == allapps.count()

    new_discount = FlexiblePriceTierFactory(
        courseware_object=flexible_price_application.courseware_object
    ).discount
    financial_assistance_request_data = {
        "status": "approved",
        "justification": "Documents in order",
        "discount": {"id": new_discount.id},
    }
    resp = admin_drf_client.patch(
        reverse(
            "fp_admin_flexiblepricing_api-detail",
            kwargs={"pk": flexible_price_application.id},
        ),
        financial_assistance_request_data,
    )
    assert resp.status_code == 200
    assert (
        models.FlexiblePrice.objects.get(
            id=flexible_price_application.id
        ).tier.discount_id
        == new_discount.id
    )
