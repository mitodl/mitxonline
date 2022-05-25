"""
Test for management command generating exchange rates
"""
from unittest.mock import patch

from django.test import TestCase
from django.test.utils import override_settings

from flexiblepricing.constants import get_currency_exchange_rate_api_request_url
from flexiblepricing.management.commands import update_exchange_rates
from flexiblepricing.models import CurrencyExchangeRate


@patch("flexiblepricing.tasks.requests.get")
class GenerateExchangeRatesTest(TestCase):
    """
    Tests for generate_exchange_rates management command
    """

    @classmethod
    def setUpTestData(cls):
        cls.command = update_exchange_rates.Command()

    def setUp(self):
        super(GenerateExchangeRatesTest, self).setUp()
        self.data = {
            "extraneous information": "blah blah blah",
            "rates": {"CBA": "3.5", "FED": "1.9", "RQP": "0.5"},
        }

    @override_settings(
        OPEN_EXCHANGE_RATES_APP_ID="foo_id",
        OPEN_EXCHANGE_RATES_URL="http://foo.bar.com",
    )
    def test_currency_exchange_rate_command(self, mocked_request):
        """
        Assert currency exchange rates are created using management command
        """
        mocked_request.return_value.json.return_value = self.data
        mocked_request.return_value.status_code = 200
        assert CurrencyExchangeRate.objects.count() == 0
        self.command.handle("generate_exchange_rates")
        called_args, _ = mocked_request.call_args
        assert called_args[0] == get_currency_exchange_rate_api_request_url()
        assert CurrencyExchangeRate.objects.count() == 3
        currency_cba = CurrencyExchangeRate.objects.get(currency_code="CBA")
        assert currency_cba.exchange_rate == 3.5
        currency_fed = CurrencyExchangeRate.objects.get(currency_code="FED")
        assert currency_fed.exchange_rate == 1.9
        currency_rqp = CurrencyExchangeRate.objects.get(currency_code="RQP")
        assert currency_rqp.exchange_rate == 0.5
