"""
Test for flexible pricing celery tasks
"""

from unittest.mock import patch

import pytest
from django.test import TestCase, override_settings
from django.urls import reverse

from courses.factories import CourseRunFactory
from ecommerce.factories import ProductFactory
from flexiblepricing.constants import FlexiblePriceStatus
from flexiblepricing.exceptions import (
    ExceededAPICallsException,
    UnexpectedAPIErrorException,
)
from flexiblepricing.factories import FlexiblePriceFactory
from flexiblepricing.models import CurrencyExchangeRate
from flexiblepricing.tasks import sync_currency_exchange_rates


class TaskConfigurationTest(TestCase):
    """
    Test cases for configuration of flexible pricing tasks.
    """

    @override_settings(
        OPEN_EXCHANGE_RATES_URL=None,
        OPEN_EXCHANGE_RATES_APP_ID=None,
    )
    def test_unset_currency_exchange_api_url(self):
        """
        Assert that the task raises an exception if it is misconfigured.
        """
        with self.assertRaises(RuntimeError) as context:  # noqa: PT027
            sync_currency_exchange_rates()
        assert "Currency exchange API URL cannot be determined" in str(
            context.exception
        )


@override_settings(
    OPEN_EXCHANGE_RATES_URL="https://openexchangerates.org/api/",
    OPEN_EXCHANGE_RATES_APP_ID="fakeID123",
)
@patch("flexiblepricing.tasks.requests.get")
class TasksTest(TestCase):
    """
    Tests for periodic task which which updates currency exchange rates from Open
    Exchange Rates.
    """

    @classmethod
    def setUpTestData(cls):
        super(TasksTest, cls).setUpTestData()  # noqa: UP008
        CurrencyExchangeRate.objects.create(currency_code="DEF", exchange_rate=1.8)
        CurrencyExchangeRate.objects.create(currency_code="MNO", exchange_rate=2.1)

    def setUp(self):
        super().setUp()
        self.data = {
            "extraneous information": "blah blah blah",
            "rates": {"DEF": "2", "MNO": "1.7", "PQR": "0.4"},
        }

    def test_update_and_add_currency_exchange_rates(self, mocked_request):
        """
        Assert currency exchange rates are updated and added
        """
        mocked_request.return_value.json.return_value = self.data
        mocked_request.return_value.status_code = 200
        assert CurrencyExchangeRate.objects.count() == 2
        sync_currency_exchange_rates.apply(args=()).get()
        called_args, _ = mocked_request.call_args
        assert (
            called_args[0]
            == "https://openexchangerates.org/api/latest.json?app_id=fakeID123"
        )
        assert CurrencyExchangeRate.objects.count() == len(self.data["rates"])
        for code, rate in self.data["rates"].items():
            currency = CurrencyExchangeRate.objects.get(currency_code=code)
            assert currency.exchange_rate == float(rate)

    def test_delete_currency_exchange_rate(self, mocked_request):
        """
        Assert currency exchange rates not in latest rate list are deleted
        """
        self.data["rates"] = {"DEF": "1.9"}
        mocked_request.return_value.json.return_value = self.data
        mocked_request.return_value.status_code = 200
        assert CurrencyExchangeRate.objects.count() == 2
        sync_currency_exchange_rates.apply(args=()).get()
        called_args, _ = mocked_request.call_args
        assert (
            called_args[0]
            == "https://openexchangerates.org/api/latest.json?app_id=fakeID123"
        )
        assert CurrencyExchangeRate.objects.count() == 1
        for code, rate in self.data["rates"].items():
            currency = CurrencyExchangeRate.objects.get(currency_code=code)
            assert currency.exchange_rate == float(rate)

    def test_exchange_rate_unexpected_api_error(self, mocked_request):
        """
        Test that the Unexpected API Error Exception is raised for an exception from
        Open Exchange Rates API
        """
        mocked_request.return_value.status_code = 401
        mocked_request.return_value.json.return_value = {
            "description": "Invalid App ID"
        }
        with self.assertRaises(UnexpectedAPIErrorException) as context:  # noqa: PT027
            sync_currency_exchange_rates.apply(args=()).get()
        assert str(context.exception) == "Invalid App ID"

    def test_exchange_rate_exceeded_api_calls(self, mocked_request):
        """
        Test that the Exceeded API Calls Exception is raised when the maximum number of monthly
        API calls to Open Exchange Rates is exceeded
        """
        mocked_request.return_value.status_code = 429
        mocked_request.return_value.json.return_value = {
            "description": "Too many calls"
        }
        with self.assertRaises(ExceededAPICallsException) as context:  # noqa: PT027
            sync_currency_exchange_rates.apply(args=()).get()
        assert str(context.exception) == "Too many calls"


pytestmark = [pytest.mark.django_db]


@pytest.fixture
def flexprice():
    """
    This does a little extra processing to make sure there is a product
    associated with the courseware object that the FlexiblePriceFactory creates
    as some of the status change emails reference it.
    """
    flexible_price_request = FlexiblePriceFactory.create()
    product = ProductFactory.create()
    courserun = CourseRunFactory.create()

    flexible_price_request.courseware_object = courserun.course
    flexible_price_request.save()

    product.purchasable_object = courserun
    product.save()

    return flexible_price_request


@pytest.mark.parametrize(
    "status",
    [
        FlexiblePriceStatus.APPROVED,
        FlexiblePriceStatus.RESET,
        FlexiblePriceStatus.PENDING_MANUAL_APPROVAL,
    ],
)
def test_flexible_price_status_change_email(status, flexprice, admin_drf_client):
    with patch(
        "flexiblepricing.tasks.notify_flexible_price_status_change_email.delay"
    ) as mocked_mailer:
        response = admin_drf_client.patch(
            f"/api/v0/flexible_pricing/applications_admin/{flexprice.id}/",
            {"status": status},
        )

        assert response.status_code < 300
        mocked_mailer.assert_called()


@pytest.mark.parametrize(
    "status",
    [
        FlexiblePriceStatus.APPROVED,
        FlexiblePriceStatus.RESET,
        FlexiblePriceStatus.PENDING_MANUAL_APPROVAL,
        FlexiblePriceStatus.DENIED,
    ],
)
def test_financial_assistance_denied_email(status, flexprice, admin_drf_client):
    """
    Tests `notify_financial_assistance_request_denied_email` is called when financial assistance request is denied.
    """
    with patch(
        "flexiblepricing.tasks.notify_financial_assistance_request_denied_email.delay"
    ) as mocked_mailer:
        response = admin_drf_client.patch(
            reverse("fp_admin_flexiblepricing_api-detail", kwargs={"pk": flexprice.id}),
            {"status": status},
        )

        assert response.status_code < 300

        if status == FlexiblePriceStatus.DENIED:
            mocked_mailer.assert_called()
        else:
            mocked_mailer.assert_not_called()
