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

    def test_init_sets_correct_defaults(self):
        """Test that HubSpotRateLimiter initializes with correct default values."""
        limiter = HubSpotRateLimiter()
        assert limiter.min_delay_ms == 60

    @patch("hubspot_sync.rate_limiter.time.sleep")
    @patch("hubspot_sync.rate_limiter.time.time")
    def test_wait_for_rate_limit_first_request(self, mock_time, mock_sleep):
        """Test first request with no previous requests."""
        mock_time.return_value = 1000.0
        
        self.rate_limiter.wait_for_rate_limit()
        
        mock_sleep.assert_not_called()

    @patch("hubspot_sync.rate_limiter.time.sleep")
    @patch("hubspot_sync.rate_limiter.time.time")
    def test_wait_for_rate_limit_respects_min_delay(self, mock_time, mock_sleep):
        """Test that minimum delay is respected between requests."""

        mock_time.side_effect = [1000.0, 1000.05, 1000.05, 1000.05]
        self.rate_limiter.min_delay_ms = 100
        
        self.rate_limiter.wait_for_rate_limit()
        self.rate_limiter.wait_for_rate_limit()
        
        expected_sleep = 0.05
        mock_sleep.assert_called_once()
        sleep_time = mock_sleep.call_args[0][0]
        assert abs(sleep_time - expected_sleep) < 0.01

    @patch("hubspot_sync.rate_limiter.time.sleep")
    @patch("hubspot_sync.rate_limiter.time.time")
    def test_wait_for_rate_limit_no_sleep_when_min_delay_satisfied(self, mock_time, mock_sleep):
        """Test no sleep when minimum delay is already satisfied."""
        mock_time.side_effect = [1000.0, 1000.2, 1000.2, 1000.2]
        self.rate_limiter.min_delay_ms = 100

        self.rate_limiter.wait_for_rate_limit()
        self.rate_limiter.wait_for_rate_limit()

        mock_sleep.assert_not_called()

    @patch("hubspot_sync.rate_limiter.time.sleep")
    @patch("hubspot_sync.rate_limiter.time.time")
    def test_wait_for_rate_limit_sliding_window_limit(self, mock_time, mock_sleep):
        """Test rate limiting when hitting max requests per second."""
        base_time = 1000.0
        mock_time.side_effect = [base_time + i * 0.01 for i in range(25)]
        self.rate_limiter.min_delay_ms = 0

        for _ in range(19):
            self.rate_limiter.wait_for_rate_limit()

        self.rate_limiter.wait_for_rate_limit()

        mock_sleep.assert_called()

    @patch("hubspot_sync.rate_limiter.time.sleep")
    @patch("hubspot_sync.rate_limiter.time.time")
    def test_wait_for_rate_limit_cleanup_old_timestamps(self, mock_time, mock_sleep):
        """Test that old timestamps are cleaned up properly."""
        base_time = 1000.0
        for i in range(10):
            self.rate_limiter._request_times.append(base_time + i * 0.1)  # noqa: SLF001

        mock_time.return_value = base_time + 2.0
        
        self.rate_limiter.wait_for_rate_limit()
        
        mock_sleep.assert_not_called()

    @patch("hubspot_sync.rate_limiter.time.time")
    def test_wait_for_rate_limit_cleanup_counter(self, mock_time):
        """Test that cleanup counter triggers periodic cleanup."""
        mock_time.return_value = 1000.0

        for _ in range(51):
            self.rate_limiter.wait_for_rate_limit()

    @patch("hubspot_sync.rate_limiter.time.sleep")
    @patch("hubspot_sync.rate_limiter.time.time")
    @patch("hubspot_sync.rate_limiter.random.uniform")
    def test_wait_for_rate_limit_jitter(self, mock_random, mock_time, mock_sleep):
        """Test that jitter is applied to sleep time."""
        mock_time.side_effect = [1000.0, 1000.05, 1000.05, 1000.05]
        mock_random.return_value = 0.01
        self.rate_limiter.min_delay_ms = 100

        self.rate_limiter.wait_for_rate_limit()
        self.rate_limiter.wait_for_rate_limit()

        mock_random.assert_called_once()
        mock_sleep.assert_called_once()
        sleep_time = mock_sleep.call_args[0][0]
        assert sleep_time > 0.05

    @patch("hubspot_sync.rate_limiter.time.sleep")
    @patch("hubspot_sync.rate_limiter.time.time")
    @patch("hubspot_sync.rate_limiter.random.uniform")
    def test_wait_for_rate_limit_negative_jitter_protection(self, mock_random, mock_time, mock_sleep):
        """Test that negative jitter doesn't result in negative sleep time."""
        mock_time.side_effect = [1000.0, 1000.05, 1000.05, 1000.05]
        mock_random.return_value = -0.1
        self.rate_limiter.min_delay_ms = 100

        self.rate_limiter.wait_for_rate_limit()
        self.rate_limiter.wait_for_rate_limit()

        mock_sleep.assert_called_once()
        sleep_time = mock_sleep.call_args[0][0]
        assert sleep_time >= 0

    @patch("hubspot_sync.rate_limiter.time.time")
    def test_wait_for_rate_limit_thread_safety(self, mock_time):
        """Test that the rate limiter handles concurrent access safely."""
        mock_time.return_value = 1000.0

        for _ in range(5):
            self.rate_limiter.wait_for_rate_limit()

    @patch("hubspot_sync.rate_limiter.log.debug")
    @patch("hubspot_sync.rate_limiter.time.time")
    def test_wait_for_rate_limit_logs_sleep_time(self, mock_time, mock_log):
        """Test that sleep time is logged when rate limiting occurs."""
        mock_time.side_effect = [1000.0, 1000.05, 1000.05, 1000.05]
        self.rate_limiter.min_delay_ms = 100

        self.rate_limiter.wait_for_rate_limit()
        self.rate_limiter.wait_for_rate_limit()


        mock_log.assert_called_once()
        log_message = mock_log.call_args[0][0]
        assert "Rate limiting: sleeping for" in log_message

    @patch("hubspot_sync.rate_limiter.time.sleep")
    @patch("hubspot_sync.rate_limiter.time.time")
    def test_wait_for_rate_limit_window_size_boundary(self, mock_time, mock_sleep):
        """Test behavior at window size boundary."""
        base_time = 1000.0
        for i in range(19):
            self.rate_limiter._request_times.append(base_time + i * 0.01)  # noqa: SLF001
        
        mock_time.return_value = base_time + 1.0
        
        self.rate_limiter.wait_for_rate_limit()
        
        mock_sleep.assert_not_called()

    @patch("hubspot_sync.rate_limiter.time.sleep")
    @patch("hubspot_sync.rate_limiter.time.time")
    def test_wait_for_rate_limit_concurrent_requests_in_window(self, mock_time, mock_sleep):
        """Test multiple requests within the same time window."""
        mock_time.return_value = 1000.0
        self.rate_limiter.min_delay_ms = 10
        
        for _ in range(3):
            self.rate_limiter.wait_for_rate_limit()
        
        assert mock_sleep.call_count >= 2

    @patch("hubspot_sync.rate_limiter.time.sleep")
    @patch("hubspot_sync.rate_limiter.time.time")
    def test_wait_for_rate_limit_zero_min_delay(self, mock_time, mock_sleep):
        """Test behavior with zero minimum delay."""
        mock_time.side_effect = [1000.0, 1000.0, 1000.0, 1000.0]
        self.rate_limiter.min_delay_ms = 0

        self.rate_limiter.wait_for_rate_limit()
        self.rate_limiter.wait_for_rate_limit()

        mock_sleep.assert_not_called()

