import logging

from django.test import TestCase

from flexiblepricing.constants import FlexiblePriceStatus
from flexiblepricing.factories import FlexiblePriceFactory
from flexiblepricing.signals import (
    _should_process_flexible_price,
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
