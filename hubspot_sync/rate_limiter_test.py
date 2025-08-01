"""Tests for hubspot_sync.rate_limiter"""

from unittest.mock import patch

from django.test import override_settings

from hubspot_sync.rate_limiter import (
    HubSpotRateLimiter,
    wait_for_hubspot_rate_limit,
)


class TestHubSpotRateLimiter:
    """Test cases for the HubSpotRateLimiter class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.rate_limiter = HubSpotRateLimiter()

    @override_settings(HUBSPOT_TASK_DELAY=100)
    def test_init_with_custom_delay(self):
        """Test that HubSpotRateLimiter initializes with custom delay setting."""
        limiter = HubSpotRateLimiter()
        assert limiter.min_delay_ms == 100

    def test_init_with_default_delay(self):
        """Test that HubSpotRateLimiter initializes with default delay when setting not found."""
        with patch("hubspot_sync.rate_limiter.getattr", return_value=60):
            limiter = HubSpotRateLimiter()
            assert limiter.min_delay_ms == 60

    @patch("hubspot_sync.rate_limiter.time.sleep")
    @patch("hubspot_sync.rate_limiter.time.time")
    def test_wait_for_rate_limit_no_headers(self, mock_time, mock_sleep):
        """Test rate limiting with no headers uses minimum delay."""
        mock_time.return_value = 0

        self.rate_limiter.last_request_time = 0
        self.rate_limiter.min_delay_ms = 100

        self.rate_limiter.wait_for_rate_limit()

        mock_sleep.assert_called_once_with(0.1)

    @patch("hubspot_sync.rate_limiter.time.sleep")
    @patch("hubspot_sync.rate_limiter.time.time")
    def test_wait_for_rate_limit_no_sleep_needed(self, mock_time, mock_sleep):
        """Test that no sleep occurs if enough time has already passed."""
        mock_time.side_effect = [0.15, 0.2, 0.3, 0.4, 0.5]

        self.rate_limiter.last_request_time = 0
        self.rate_limiter.min_delay_ms = 100

        self.rate_limiter.wait_for_rate_limit()

        mock_sleep.assert_not_called()

    @patch("hubspot_sync.rate_limiter.time.sleep")
    @patch("hubspot_sync.rate_limiter.time.time")
    def test_wait_for_rate_limit_updates_last_request_time(self, mock_time, mock_sleep):  # noqa: ARG002
        """Test that last_request_time is updated after waiting."""
        mock_time.return_value = 2.0

        self.rate_limiter.last_request_time = 0
        self.rate_limiter.wait_for_rate_limit()

        assert self.rate_limiter.last_request_time == 2.0


class TestModuleFunctions:
    """Test module-level functions."""

    @patch("hubspot_sync.rate_limiter.rate_limiter.wait_for_rate_limit")
    def test_wait_for_hubspot_rate_limit(self, mock_wait):
        """Test the convenience function calls the rate limiter."""
        wait_for_hubspot_rate_limit()

        mock_wait.assert_called_once_with()

    @patch("hubspot_sync.rate_limiter.rate_limiter.wait_for_rate_limit")
    def test_wait_for_hubspot_rate_limit_no_headers(self, mock_wait):
        """Test the convenience function with no headers."""
        wait_for_hubspot_rate_limit()

        mock_wait.assert_called_once_with()
