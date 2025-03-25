import logging
from unittest.mock import patch

from django.test import TestCase

from ecommerce.factories import DiscountFactory
from flexiblepricing.constants import FlexiblePriceStatus
from flexiblepricing.factories import FlexiblePriceFactory
from flexiblepricing.models import FlexiblePrice
from flexiblepricing.signals import (
    _calculate_discount_amount,
    _create_discount_api_call,
    _get_valid_product_id,
    _process_flexible_price_discount,
    _should_process_flexible_price,
    _validate_course_run,
    _validate_courseware_object,
    handle_flexible_price_save,
)


class TestFlexiblePriceSignals(TestCase):
    """Tests for flexible pricing signals"""

    def setUp(self):
        self.logger = logging.getLogger("flexiblepricing.signals")
        self.original_logger_level = self.logger.level
        self.logger.setLevel(logging.CRITICAL)  # Silence logs during tests

    def tearDown(self):
        self.logger.setLevel(self.original_logger_level)

    def test_should_process_flexible_price_valid_statuses(self):
        """Test that approved statuses return True"""
        for status in [FlexiblePriceStatus.APPROVED, FlexiblePriceStatus.AUTO_APPROVED]:
            fp = FlexiblePriceFactory(status=status)
            assert _should_process_flexible_price(fp) is True

    def test_should_process_flexible_price_invalid_statuses(self):
        """Test that non-approved statuses return False"""
        fp = FlexiblePriceFactory(status=FlexiblePriceStatus.CREATED)
        assert _should_process_flexible_price(fp) is False

    def test_validate_courseware_object_with_object(self):
        """Test validation with courseware object"""
        fp = FlexiblePriceFactory()
        assert _validate_courseware_object(fp) is not None

    def test_validate_courseware_object_without_object(self):
        """Test validation without courseware object"""
        fp = FlexiblePriceFactory()
        fp.courseware_object = None
        assert _validate_courseware_object(fp) is None

    def test_validate_course_run_valid(self):
        """Test validation with valid course run"""
        class MockCourseware:
            first_unexpired_run = type("Run", (), {"courseware_id": "test"})
        courseware = MockCourseware()
        assert _validate_course_run(courseware, 1) is not None

    def test_validate_course_run_invalid(self):
        """Test validation with invalid course run"""
        class MockCourseware:
            first_unexpired_run = None
        courseware = MockCourseware()
        assert _validate_course_run(courseware, 1) is None

    @patch("flexiblepricing.signals.logger")
    def test_validate_course_run_logs_warning(self, mock_logger):
        """Test that invalid course run logs warning"""
        class MockCourseware:
            first_unexpired_run = None
        _validate_course_run(MockCourseware(), 1)
        mock_logger.warning.assert_called_once()

    @patch("flexiblepricing.signals.get_ecommerce_products_by_courseware_name")
    def test_get_valid_product_id_success(self, mock_get_products):
        """Test successful product ID retrieval"""
        mock_get_products.return_value = [{"id": "test-id"}]
        assert _get_valid_product_id("course-id", 1) == "test-id"

    @patch("flexiblepricing.signals.get_ecommerce_products_by_courseware_name")
    def test_get_valid_product_id_no_products(self, mock_get_products):
        """Test no products case"""
        mock_get_products.return_value = []
        assert _get_valid_product_id("course-id", 1) is None

    @patch("flexiblepricing.signals.get_ecommerce_products_by_courseware_name")
    def test_get_valid_product_id_invalid_structure(self, mock_get_products):
        """Test invalid product structure"""
        mock_get_products.return_value = [{"no_id": "test"}]
        assert _get_valid_product_id("course-id", 1) is None

    @patch("flexiblepricing.signals.logger")
    @patch("flexiblepricing.signals.get_ecommerce_products_by_courseware_name")
    def test_get_valid_product_id_logs_error(self, mock_get_products, mock_logger):
        """Test that errors are logged"""
        mock_get_products.return_value = [{"no_id": "test"}]
        _get_valid_product_id("course-id", 1)
        mock_logger.error.assert_called_once()

    def test_calculate_discount_amount_success(self):
        """Test successful discount calculation"""
        class MockProduct:
            def exists(self):
                return True
            def first(self):
                return "product"
        
        class MockCourseware:
            active_products = MockProduct()
        
        discount = DiscountFactory(amount=100)
        
        with patch(
            "flexiblepricing.signals.determine_courseware_flexible_price_discount",
            return_value=discount
        ):
            fp = FlexiblePriceFactory()
            courseware = MockCourseware()
            assert _calculate_discount_amount(courseware, fp) == 100.0

    def test_calculate_discount_amount_no_active_products(self):
        """Test case with no active products"""
        class MockCourseware:
            active_products = None
        
        fp = FlexiblePriceFactory()
        assert _calculate_discount_amount(MockCourseware(), fp) is None

    @patch("flexiblepricing.signals.determine_courseware_flexible_price_discount")
    def test_calculate_discount_amount_invalid_result(self, mock_determine):
        """Test invalid discount result"""
        mock_determine.return_value = None
        
        class MockProduct:
            def exists(self):
                return True
            def first(self):
                return "product"
        
        class MockCourseware:
            active_products = MockProduct()
        
        fp = FlexiblePriceFactory()
        assert _calculate_discount_amount(MockCourseware(), fp) is None

    @patch("flexiblepricing.signals.requests.post")
    @patch("flexiblepricing.signals.settings",
           UNIFIED_ECOMMERCE_URL="http://test.com",
           UNIFIED_ECOMMERCE_API_KEY="test-key")
    def test_create_discount_api_call_success(self, mock_settings, mock_post):
        """Test successful API call"""
        mock_response = type("Response", (), {"status_code": 201})
        mock_post.return_value = mock_response
        
        fp = FlexiblePriceFactory(user__email="test@example.com")
        _create_discount_api_call(fp, "product-id", 100)
        
        assert mock_post.called
        assert "test@example.com" in mock_post.call_args[1]["json"]["users"]

    @patch("flexiblepricing.signals.requests.post")
    @patch("flexiblepricing.signals.settings",
           UNIFIED_ECOMMERCE_URL="http://test.com",
           UNIFIED_ECOMMERCE_API_KEY="test-key")
    def test_create_discount_api_call_failure(self, mock_settings, mock_post):
        """Test failed API call"""
        mock_response = type("Response", (), {"status_code": 400})
        mock_post.return_value = mock_response

        fp = FlexiblePriceFactory(user__email="test@example.com")
        _create_discount_api_call(fp, "product-id", 100)

        assert mock_post.called

    @patch("flexiblepricing.signals.logger")
    @patch("flexiblepricing.signals._process_flexible_price_discount")
    def test_handle_flexible_price_save_approved(self, mock_process, mock_logger):
        """Test that approved status triggers processing"""
        FlexiblePriceFactory(status=FlexiblePriceStatus.APPROVED)
        mock_process.assert_called_once()

    @patch("flexiblepricing.signals._process_flexible_price_discount")
    def test_handle_flexible_price_save_not_approved(self, mock_process):
        """Test that non-approved status doesn't trigger processing"""
        FlexiblePriceFactory(status=FlexiblePriceStatus.CREATED)
        mock_process.assert_not_called()

    @patch("flexiblepricing.signals.logger")
    @patch("flexiblepricing.signals._process_flexible_price_discount", side_effect=ValueError("test"))
    def test_handle_flexible_price_save_error(self, mock_process, mock_logger):
        """Test that errors are logged"""
        FlexiblePriceFactory(status=FlexiblePriceStatus.APPROVED)
        mock_logger.critical.assert_called_once()

    @patch("flexiblepricing.signals._validate_courseware_object")
    @patch("flexiblepricing.signals._validate_course_run")
    @patch("flexiblepricing.signals._get_valid_product_id")
    @patch("flexiblepricing.signals._calculate_discount_amount")
    @patch("flexiblepricing.signals._create_discount_api_call")
    def test_process_flexible_price_discount_full_flow(
        self, mock_create, mock_calc, mock_product, mock_run, mock_courseware
    ):
        """Test the full processing flow with all steps successful"""
        mock_courseware.return_value = "courseware"
        mock_run.return_value = type("Run", (), {"courseware_id": "test"})
        mock_product.return_value = "product-id"
        mock_calc.return_value = 100

        fp = FlexiblePriceFactory(status=FlexiblePriceStatus.APPROVED)

        mock_create.assert_called_once_with(fp, "product-id", 100)
