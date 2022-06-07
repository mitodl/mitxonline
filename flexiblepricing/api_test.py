"""Flexible price api tests"""
from datetime import timedelta
import ddt
import json
import pytest

from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase
from mitol.common.utils.datetime import now_in_utc

from courses.factories import ProgramFactory, CourseFactory, CourseRunFactory
from flexiblepricing.api import (
    parse_country_income_thresholds,
    IncomeThreshold,
    import_country_income_thresholds,
    update_currency_exchange_rate,
    determine_tier_courseware,
    determine_income_usd,
    determine_auto_approval,
)
from flexiblepricing.constants import FlexiblePriceStatus
from flexiblepricing.exceptions import CountryIncomeThresholdException
from flexiblepricing.factories import FlexiblePriceFactory, FlexiblePriceTierFactory
from flexiblepricing.models import (
    CountryIncomeThreshold,
    CurrencyExchangeRate,
    # FlexiblePriceTier,
)


def test_parse_country_income_thresholds_no_header(tmp_path):
    """parse_country_income_thresholds should throw error if no header is found"""
    path = tmp_path / "test.csv"
    open(path, "w")  # create a file
    with pytest.raises(CountryIncomeThresholdException) as exc:
        parse_country_income_thresholds(path)

    assert exc.value.args[0] == "Unable to find the header row"


def test_parse_country_income_thresholds_missing_header_fields(tmp_path):
    """parse_country_income_thresholds should throw error if any of the header field is missing"""
    path = tmp_path / "test.csv"
    with open(path, "w") as file:
        file.write("country\n")
        file.write("PK\n")

    with pytest.raises(CountryIncomeThresholdException) as exc:
        parse_country_income_thresholds(path)

    assert exc.value.args[0] == "Unable to find column header income"


def test_parse_country_income_thresholds(tmp_path):
    """parse_country_income_thresholds should convert CSV records into IncomeThreshold objects"""
    path = tmp_path / "test.csv"
    with open(path, "w") as file:
        file.write("country,income\n")
        file.write("PK,25000\n")
        file.write("US,75000\n")

    income_thresholds = parse_country_income_thresholds(path)
    assert income_thresholds == [
        IncomeThreshold(country="PK", income="25000"),
        IncomeThreshold(country="US", income="75000"),
    ]


@pytest.mark.django_db
def test_import_country_income_thresholds(tmp_path, caplog):
    """test import_country_income_thresholds works fine"""
    path = tmp_path / "test.csv"
    with open(path, "w") as file:
        file.write("country,income\n")
        file.write("PK,25000\n")
        file.write("US,75000\n")

    # first time would create new records
    import_country_income_thresholds(path)
    assert "Record created successfully for country=PK with income 25000"
    assert "Record created successfully for country=US with income 75000"

    # second time would rather update records
    import_country_income_thresholds(path)
    assert "Updated record successfully for country=PK with income 25000"
    assert "Updated record successfully for country=US with income 75000"


class ExchangeRateAPITests(TestCase):
    """
    Tests for flexible pricing exchange rate api backend
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        CurrencyExchangeRate.objects.create(currency_code="ABC", exchange_rate=1.5)
        CurrencyExchangeRate.objects.create(currency_code="DEF", exchange_rate=1.5)

    def test_update_currency_exchange_rate(self):
        """
        Tests updated_currency_exchange_rate()
        """
        latest_rates = {"ABC": 12.3, "GHI": 7.89}
        update_currency_exchange_rate(latest_rates)
        assert (
            CurrencyExchangeRate.objects.get(currency_code="ABC").exchange_rate
            == latest_rates["ABC"]
        )
        with self.assertRaises(CurrencyExchangeRate.DoesNotExist):
            CurrencyExchangeRate.objects.get(currency_code="DEF")
        assert (
            CurrencyExchangeRate.objects.get(currency_code="GHI").exchange_rate
            == latest_rates["GHI"]
        )


def create_courseware(create_tiers=True, past=False):
    """
    Helper function to create a flexible pricing courseware
    Returns:
        courses.models.Program: A new program
    """
    end_date = None
    program = ProgramFactory.create(live=True)
    course = CourseFactory.create(program=program)

    if past:
        end_date = now_in_utc() - timedelta(days=100)
    else:
        end_date = now_in_utc() + timedelta(days=100)

    CourseRunFactory.create(
        end_date=end_date,
        enrollment_end=now_in_utc() + timedelta(hours=1),
        course=course,
    )
    tiers = None
    if create_tiers:
        tiers = {
            "0k": FlexiblePriceTierFactory.create(
                courseware_object=course, income_threshold_usd=0, current=True
            ),
            "25k": FlexiblePriceTierFactory.create(
                courseware_object=course, income_threshold_usd=25000, current=True
            ),
            "50k": FlexiblePriceTierFactory.create(
                courseware_object=course, income_threshold_usd=50000, current=True
            ),
            "75k": FlexiblePriceTierFactory.create(
                courseware_object=course,
                income_threshold_usd=75000,
                current=True,
                discount__amount=0,
            ),
        }
    return course, tiers


class FlexiblePriceBaseTestCase(TestCase):
    """
    Base test case for financial aid test setup
    """

    @classmethod
    def setUpTestData(cls):
        # replace imported thresholds with fake ones created here
        CountryIncomeThreshold.objects.all().delete()

        cls.course, cls.tiers = create_courseware()
        cls.country_income_threshold_0 = CountryIncomeThreshold.objects.create(
            country_code="0",
            income_threshold=0,
        )
        CountryIncomeThreshold.objects.create(
            country_code="50",
            income_threshold=50000,
        )

        # Create a FinancialAid with a reset status to verify that it is ignored
        FlexiblePriceFactory.create(
            # user="US",
            tier=cls.tiers["75k"],
            status=FlexiblePriceStatus.RESET,
        )

    @staticmethod
    def make_http_request(
        method, url, status, data=None, content_type="application/json", **kwargs
    ):
        """
        Helper method for asserting an HTTP status. Returns the response for further tests if needed.
        Args:
            method (method): which http method to use (e.g. self.client.put)
            url (str): url for request
            status (int): http status code
            data (dict): data for request
            content_type (str): content_type for request
            **kwargs: any additional kwargs to pass into method
        Returns:
            rest_framework.response.Response
        """
        if data is not None:
            kwargs["data"] = json.dumps(data)
        resp = method(url, content_type=content_type, **kwargs)
        assert resp.status_code == status
        return resp


@ddt.ddt
class FlexiblePricAPITests(FlexiblePriceBaseTestCase):
    """
    Tests for financialaid api backend
    """

    def setUp(self):
        super().setUp()
        self.course.refresh_from_db()

    @ddt.data(
        [0, "0k"],
        [1000, "0k"],
        [25000, "25k"],
        [27500, "25k"],
        [50000, "50k"],
        [72800, "50k"],
        [75000, "75k"],
        [34938234, "75k"],
    )
    @ddt.unpack
    def test_determine_tier_courseware(self, income, expected_tier_key):
        """
        Tests determine_tier_courseware() assigning the correct tiers. This should assign the tier where the tier's
        income threshold is equal to or less than income.
        """
        assert (
            determine_tier_courseware(self.course, income)
            == self.tiers[expected_tier_key]
        )

    def test_determine_tier_courseware_not_current(self):
        """
        A current=False tier should be ignored
        """
        not_current = FlexiblePriceTierFactory.create(
            courseware_object=self.course, income_threshold_usd=75000, current=False
        )
        assert determine_tier_courseware(self.course, 34938234) != not_current

    def test_determine_tier_courseware_improper_setup(self):
        """
        Tests that determine_tier_courseware() raises ImproperlyConfigured if no $0-discount TierProgram
        has been created and income supplied is too low.
        """
        program = ProgramFactory.create()
        course = CourseFactory.create(program=program)
        with self.assertRaises(ImproperlyConfigured):
            determine_tier_courseware(course, 0)

    @ddt.data(
        [0, "0", True],
        [1, "0", True],
        [0, "50", False],
        [49999, "50", False],
        [50000, "50", False],
        [50001, "50", True],
    )
    @ddt.unpack
    def test_determine_auto_approval(self, income_usd, country_code, expected):
        """
        Tests determine_auto_approval() assigning the correct auto-approval status. This should return True
        if income is strictly greater than the threshold (or if the threshold is 0, which is inclusive of 0).
        """
        flexible_price = FlexiblePriceFactory.create(
            income_usd=income_usd,
            country_of_income=country_code,
        )
        courseware = determine_tier_courseware(self.course, income_usd)
        assert determine_auto_approval(flexible_price, courseware) is expected

    def test_determine_income_usd_from_not_usd(self):
        """
        Tests determine_income_usd() from a non-USD currency
        """
        CurrencyExchangeRate.objects.create(currency_code="GHI", exchange_rate=1.5)
        assert determine_income_usd(3000, "GHI") == 2000

    def test_determine_income_usd_from_usd(self):
        """
        Tests determine_income_usd() from a USD currency
        """
        # Note no CurrencyExchangeRate created here
        assert determine_income_usd(5000, "USD") == 5000
