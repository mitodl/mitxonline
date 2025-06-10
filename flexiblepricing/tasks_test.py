"""
Test for flexible pricing celery tasks
"""

import logging
from unittest.mock import MagicMock, patch

import pytest
import requests
from django.core.exceptions import ObjectDoesNotExist
from django.test import TestCase, override_settings
from django.urls import reverse

from courses.factories import CourseFactory, CourseRunFactory, ProgramFactory
from ecommerce.factories import DiscountFactory, ProductFactory
from flexiblepricing.constants import FlexiblePriceStatus
from flexiblepricing.exceptions import (
    ExceededAPICallsException,
    UnexpectedAPIErrorException,
)
from flexiblepricing.factories import FlexiblePriceFactory, FlexiblePriceTierFactory
from flexiblepricing.models import CurrencyExchangeRate
from flexiblepricing.tasks import (
    _calculate_discount_amount,
    _create_discount_api_call,
    _get_valid_product_id,
    _process_course_discounts,
    _process_flexible_price_discount,
    _validate_courseware_object,
    process_flexible_price_discount_task,
    sync_currency_exchange_rates,
)
from users.factories import UserFactory


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


class TestFlexiblePriceDiscountProcessing(TestCase):
    """
    Test cases for flexible price discount processing.
    """

    def setUp(self):
        """
        Set up test data for flexible price discount processing tests.
        This includes creating a user, course, program, course run, product,
        and flexible price tier instance.
        """
        self.user = UserFactory(email="test@example.com")
        self.tier = FlexiblePriceTierFactory(
            discount=DiscountFactory(discount_type="percentage")
        )
        self.course = CourseFactory()
        self.program = ProgramFactory()
        self.program.add_requirement(self.course)
        self.course_run = CourseRunFactory(
            course=self.course, courseware_id="course-v1:test+test+test"
        )
        self.product = ProductFactory(is_active=True)
        self.course_run.products.add(self.product)

        self.logger = logging.getLogger()
        self.logger_mock = MagicMock()
        self.logger.info = self.logger_mock
        self.logger.warning = self.logger_mock
        self.logger.error = self.logger_mock
        self.logger.exception = self.logger_mock

    def test_validate_courseware_object_with_valid_object(self):
        """Test _validate_courseware_object with valid courseware object"""
        instance = FlexiblePriceFactory(courseware_object=self.course)
        result = _validate_courseware_object(instance)
        assert result == self.course

    @patch("flexiblepricing.tasks.get_ecommerce_products_by_courseware_name")
    @patch("flexiblepricing.tasks.logging.getLogger")
    def test_get_valid_product_id_success(self, mock_logger, mock_get_products):
        """Test _get_valid_product_id with valid product"""

        product = ProductFactory()
        mock_get_products.return_value = [
            {
                "id": product.id,
            }
        ]

        result = _get_valid_product_id(product.purchasable_object.id, 1)

        assert result == product.id
        mock_get_products.assert_called_once_with(product.purchasable_object.id)
        mock_logger.info.assert_not_called()

    @patch("flexiblepricing.tasks.get_ecommerce_products_by_courseware_name")
    def test_get_valid_product_id_no_products(self, mock_get_products):
        """Test _get_valid_product_id with no products"""
        mock_get_products.return_value = []
        result = _get_valid_product_id("test-course", 1)
        assert result is None
        self.logger_mock.assert_called_with(
            "No products found for FlexiblePrice ID: %s", 1
        )

    @patch("flexiblepricing.tasks.get_ecommerce_products_by_courseware_name")
    def test_get_valid_product_id_request_exception(self, mock_get_products):
        """Test _get_valid_product_id with request exception"""
        mock_get_products.side_effect = requests.exceptions.RequestException()
        result = _get_valid_product_id("test-course", 1)
        assert result is None
        self.logger_mock.assert_called_with("Product retrieval failed for ID %s", 1)

    @patch("flexiblepricing.tasks.determine_courseware_flexible_price_discount")
    def test_calculate_discount_amount_success(self, mock_determine_discount):
        """Test _calculate_discount_amount with valid discount"""
        mock_discount = MagicMock(amount="10.00")
        mock_determine_discount.return_value = mock_discount
        instance = FlexiblePriceFactory(user=self.user)

        result = _calculate_discount_amount(self.course_run, instance)
        assert result == 10.0

    @patch("flexiblepricing.tasks.determine_courseware_flexible_price_discount")
    def test_calculate_discount_amount_no_discount(self, mock_determine_discount):
        """Test _calculate_discount_amount with no discount"""
        mock_determine_discount.return_value = None
        instance = FlexiblePriceFactory(user=self.user)

        result = _calculate_discount_amount(self.course_run, instance)
        assert result is None
        self.logger_mock.assert_called_with(
            "No discount found for FlexiblePrice ID: %s", instance.id
        )

    @patch("flexiblepricing.tasks.requests.post")
    @override_settings(
        UNIFIED_ECOMMERCE_URL="http://test.com", UNIFIED_ECOMMERCE_API_KEY="test-key"
    )
    def test_create_discount_api_call_success(self, mock_post):
        """Test _create_discount_api_call with successful response"""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_post.return_value = mock_response

        instance = FlexiblePriceFactory(user=self.user, tier=self.tier)
        _create_discount_api_call(instance, "product-123", 10.0)

        mock_post.assert_called_once()
        self.logger_mock.assert_called_with("Discount created for ID: %s", instance.id)

    @patch("flexiblepricing.tasks.requests.post")
    @override_settings(
        UNIFIED_ECOMMERCE_URL="http://test.com", UNIFIED_ECOMMERCE_API_KEY="test-key"
    )
    def test_create_discount_api_call_failure(self, mock_post):
        """Test _create_discount_api_call with failed response"""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_post.return_value = mock_response

        instance = FlexiblePriceFactory(user=self.user, tier=self.tier)
        _create_discount_api_call(instance, "product-123", 10.0)

        self.logger_mock.assert_called_with(
            "Discount creation failed for ID %s. Status: %s", instance.id, 400
        )

    @patch("flexiblepricing.tasks._process_course_discounts")
    @patch("flexiblepricing.tasks._validate_courseware_object")
    @patch("flexiblepricing.tasks.logging.getLogger")
    def test_process_flexible_price_discount_course(
        self, mock_get_logger, mock_validate, mock_process
    ):
        """Test _process_flexible_price_discount with course"""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        instance = FlexiblePriceFactory(courseware_object=self.course)
        mock_validate.return_value = self.course

        _process_flexible_price_discount(instance)

        mock_logger.info.assert_any_call(
            "Processing course discounts for FlexiblePrice ID: %s", instance.id
        )

        mock_process.assert_called_once_with(self.course, instance)

    @patch("flexiblepricing.tasks._process_course_discounts")
    @patch("flexiblepricing.tasks._validate_courseware_object")
    @patch("flexiblepricing.tasks.logging.getLogger")
    def test_process_flexible_price_discount_program(
        self, mock_get_logger, mock_validate, mock_process
    ):
        """Test _process_flexible_price_discount with program"""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        instance = FlexiblePriceFactory(courseware_object=self.program)
        mock_validate.return_value = self.program

        _process_flexible_price_discount(instance)

        mock_logger.info.assert_any_call(
            "Processing program discounts for FlexiblePrice ID: %s", instance.id
        )

        assert mock_process.call_count == len(self.program.courses)
        for i, course in enumerate(self.program.courses):
            args, _ = mock_process.call_args_list[i]
            assert args[0] == course[0]
            assert args[1] == instance

    @patch("flexiblepricing.tasks._process_flexible_price_discount")
    def test_process_flexible_price_discount_task_success(self, mock_process):
        """Test process_flexible_price_discount_task success"""
        instance = FlexiblePriceFactory(status=FlexiblePriceStatus.APPROVED)

        mock_process.assert_called_once()

        args, _ = mock_process.call_args
        called_instance = args[0]
        assert called_instance.id == instance.id

    @patch("flexiblepricing.tasks.FlexiblePrice.objects.get")
    def test_process_flexible_price_discount_task_error(self, mock_get):
        """Test process_flexible_price_discount_task with error"""
        mock_get.side_effect = ObjectDoesNotExist()
        process_flexible_price_discount_task(1)
        self.logger_mock.assert_called_with(
            "FlexiblePrice instance with ID %s does not exist", 1
        )

    @patch("flexiblepricing.tasks.process_flexible_price_discount_task.delay")
    @patch("flexiblepricing.tasks._get_valid_product_id")
    @patch("flexiblepricing.tasks._calculate_discount_amount")
    @patch("flexiblepricing.tasks._create_discount_api_call")
    @patch("flexiblepricing.tasks.get_enrollable_courseruns_qs")
    def test_process_course_discounts_success(
        self,
        mock_get_runs,
        mock_create,
        mock_calculate,
        mock_get_product,
        mocked_flexibleprice_discounttask,  # noqa: ARG002
    ):
        """Test _process_course_discounts with valid data"""
        mock_course_run = MagicMock()
        mock_course_run.courseware_id = "course-run-123"
        mock_course_run.products.filter.return_value = [MagicMock()]

        mock_get_runs.return_value = [mock_course_run]
        mock_get_product.return_value = "123"
        mock_calculate.return_value = 10.0

        instance = FlexiblePriceFactory(
            user=self.user, tier=self.tier, courseware_object=self.course
        )

        _process_course_discounts(self.course, instance)

        mock_get_runs.assert_called_once_with(valid_courses=[self.course])
        mock_get_product.assert_called_once_with("course-run-123", instance.id)
        mock_calculate.assert_called_once_with(mock_course_run, instance)
        mock_create.assert_called_once_with(instance, "123", 10.0)

    @patch("flexiblepricing.tasks.get_enrollable_courseruns_qs")
    def test_process_course_discounts_no_runs(self, mock_get_runs):
        """Test _process_course_discounts with no course runs"""
        mock_get_runs.return_value = []
        instance = FlexiblePriceFactory()

        _process_course_discounts(self.course, instance)

        self.logger_mock.assert_called_with(
            "No unexpired runs found for course %s", self.course.id
        )


@pytest.mark.django_db
def test_process_flexible_price_discount_task_skips(mocker, settings):
    """Test that the sync skips if there's no API key."""

    patched_task_logic = mocker.patch(
        "flexiblepricing.tasks._process_flexible_price_discount"
    )

    flex_price_id = -1
    settings.UNIFIED_ECOMMERCE_API_KEY = ""

    assert settings.UNIFIED_ECOMMERCE_API_KEY == ""

    process_flexible_price_discount_task(flex_price_id)

    patched_task_logic.assert_not_called()
