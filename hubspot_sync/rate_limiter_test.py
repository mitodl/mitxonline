"""Tests for hubspot_sync.rate_limiter"""
from unittest.mock import patch

import pytest
from django.test import override_settings

from hubspot_sync.rate_limiter import (
    HubSpotRateLimiter,
    calculate_exponential_backoff,
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
        mock_time.side_effect = [0, 0, 0.05]
        
        self.rate_limiter.last_request_time = 0
        self.rate_limiter.min_delay_ms = 100
        
        self.rate_limiter.wait_for_rate_limit()
        mock_sleep.assert_called_once_with(0.05)

    @patch("hubspot_sync.rate_limiter.time.sleep")
    @patch("hubspot_sync.rate_limiter.time.time")
    def test_wait_for_rate_limit_no_sleep_needed(self, mock_time, mock_sleep):
        """Test that no sleep occurs if enough time has already passed."""
        mock_time.side_effect = [0, 0, 0.2]
        
        self.rate_limiter.last_request_time = 0
        self.rate_limiter.min_delay_ms = 100
        
        self.rate_limiter.wait_for_rate_limit()
        
        mock_sleep.assert_not_called()

    @patch("hubspot_sync.rate_limiter.time.sleep")
    @patch("hubspot_sync.rate_limiter.time.time")
    def test_wait_for_rate_limit_with_headers_critical_secondly(self, mock_time, mock_sleep):
        """Test rate limiting when critically low on per-second requests."""
        mock_time.side_effect = [0, 0, 0]
        
        headers = {
            'x-hubspot-ratelimit-secondly-remaining': '1',
            'x-hubspot-ratelimit-secondly': '19',
            'x-hubspot-ratelimit-remaining': '150',
            'x-hubspot-ratelimit-max': '190',
            'x-hubspot-ratelimit-interval-milliseconds': '10000',
        }
        
        self.rate_limiter.last_request_time = 0
        self.rate_limiter.wait_for_rate_limit(headers)
        
        mock_sleep.assert_called_once_with(1.1)

    @patch("hubspot_sync.rate_limiter.time.sleep")
    @patch("hubspot_sync.rate_limiter.time.time")
    def test_wait_for_rate_limit_with_headers_warning_secondly(self, mock_time, mock_sleep):
        """Test rate limiting when getting close to per-second limit."""
        mock_time.side_effect = [0, 0, 0]
        
        headers = {
            'x-hubspot-ratelimit-secondly-remaining': '4',
            'x-hubspot-ratelimit-secondly': '19',
            'x-hubspot-ratelimit-remaining': '150',
            'x-hubspot-ratelimit-max': '190',
            'x-hubspot-ratelimit-interval-milliseconds': '10000',
        }
        
        self.rate_limiter.last_request_time = 0
        self.rate_limiter.wait_for_rate_limit(headers)
        
        mock_sleep.assert_called_once_with(0.25)

    @patch("hubspot_sync.rate_limiter.time.sleep")
    @patch("hubspot_sync.rate_limiter.time.time")
    def test_wait_for_rate_limit_with_headers_critical_interval(self, mock_time, mock_sleep):
        """Test rate limiting when critically low on interval requests."""
        mock_time.side_effect = [0, 0, 0]
        
        headers = {
            'x-hubspot-ratelimit-secondly-remaining': '15',
            'x-hubspot-ratelimit-secondly': '19',
            'x-hubspot-ratelimit-remaining': '8',
            'x-hubspot-ratelimit-max': '190',
            'x-hubspot-ratelimit-interval-milliseconds': '10000',
        }
        
        self.rate_limiter.last_request_time = 0
        self.rate_limiter.wait_for_rate_limit(headers)

        mock_sleep.assert_called_once_with(0.2)

    @patch("hubspot_sync.rate_limiter.time.sleep")
    @patch("hubspot_sync.rate_limiter.time.time")
    def test_wait_for_rate_limit_with_headers_normal(self, mock_time, mock_sleep):
        """Test rate limiting under normal conditions."""
        mock_time.side_effect = [0, 0, 0]
        
        headers = {
            'x-hubspot-ratelimit-secondly-remaining': '15',
            'x-hubspot-ratelimit-secondly': '19',
            'x-hubspot-ratelimit-remaining': '150',
            'x-hubspot-ratelimit-max': '190',
            'x-hubspot-ratelimit-interval-milliseconds': '10000',
        }
        
        self.rate_limiter.last_request_time = 0
        self.rate_limiter.wait_for_rate_limit(headers)
        
        expected_delay = 1000 / (19 * 0.8)
        mock_sleep.assert_called_once()
        call_args = mock_sleep.call_args[0]
        assert abs(call_args[0] - expected_delay / 1000) < 0.01

    @patch("hubspot_sync.rate_limiter.log")
    def test_calculate_delay_from_headers_invalid_data(self, mock_log):
        """Test that invalid header data falls back to minimum delay."""
        headers = {
            'x-hubspot-ratelimit-secondly-remaining': 'invalid',
            'x-hubspot-ratelimit-secondly': '19',
        }
        
        self.rate_limiter.min_delay_ms = 50
        delay = self.rate_limiter._calculate_delay_from_headers(headers)
        
        assert delay == 50
        mock_log.warning.assert_called_once()

    def test_calculate_delay_from_headers_missing_headers(self):
        """Test that missing headers use default values."""
        headers = {}
        
        delay = self.rate_limiter._calculate_delay_from_headers(headers)

        expected_delay = int(1000 / (19 * 0.8))
        assert delay == expected_delay

    @patch("hubspot_sync.rate_limiter.time.sleep")
    @patch("hubspot_sync.rate_limiter.time.time")
    def test_wait_for_rate_limit_updates_last_request_time(self, mock_time, mock_sleep):
        """Test that last_request_time is updated after waiting."""
        mock_time.side_effect = [0, 0, 0, 1.5]
        
        self.rate_limiter.last_request_time = 0
        self.rate_limiter.wait_for_rate_limit()
        
        assert self.rate_limiter.last_request_time == 1.5


class TestModuleFunctions:
    """Test module-level functions."""

    @patch("hubspot_sync.rate_limiter.rate_limiter.wait_for_rate_limit")
    def test_wait_for_hubspot_rate_limit(self, mock_wait):
        """Test the convenience function calls the rate limiter."""
        headers = {"x-hubspot-ratelimit-remaining": "100"}
        
        wait_for_hubspot_rate_limit(headers)
        
        mock_wait.assert_called_once_with(headers)

    @patch("hubspot_sync.rate_limiter.rate_limiter.wait_for_rate_limit")
    def test_wait_for_hubspot_rate_limit_no_headers(self, mock_wait):
        """Test the convenience function with no headers."""
        wait_for_hubspot_rate_limit()
        
        mock_wait.assert_called_once_with(None)

    def test_calculate_exponential_backoff_zero_attempt(self):
        """Test exponential backoff for first attempt."""
        delay = calculate_exponential_backoff(0, base_delay=60)
        assert delay == 60

    def test_calculate_exponential_backoff_multiple_attempts(self):
        """Test exponential backoff increases with attempts."""
        delays = [calculate_exponential_backoff(i, base_delay=60) for i in range(5)]
        
        expected = [60, 120, 240, 300, 300]
        assert delays == expected

    def test_calculate_exponential_backoff_custom_base(self):
        """Test exponential backoff with custom base delay."""
        delay = calculate_exponential_backoff(2, base_delay=30)
        assert delay == 120

    def test_calculate_exponential_backoff_max_cap(self):
        """Test exponential backoff respects maximum cap."""
        delay = calculate_exponential_backoff(10, base_delay=60)
        assert delay == 300


class TestIntegration:
    """Integration tests for rate limiting functionality."""

    @patch("hubspot_sync.rate_limiter.time.sleep")
    def test_realistic_rate_limiting_scenario(self, mock_sleep):
        """Test a realistic scenario with multiple API calls."""
        limiter = HubSpotRateLimiter()
        limiter.min_delay_ms = 60
        
        scenarios = [
            {
                'x-hubspot-ratelimit-secondly-remaining': '18',
                'x-hubspot-ratelimit-remaining': '180',
            },
            {
                'x-hubspot-ratelimit-secondly-remaining': '10',
                'x-hubspot-ratelimit-remaining': '100',
            },
            {
                'x-hubspot-ratelimit-secondly-remaining': '4',
                'x-hubspot-ratelimit-remaining': '50',
            },
            {
                'x-hubspot-ratelimit-secondly-remaining': '1',
                'x-hubspot-ratelimit-remaining': '20',
            },
        ]
        
        sleep_times = []
        
        with patch("hubspot_sync.rate_limiter.time.time", side_effect=[i * 2 for i in range(20)]):
            for i, headers in enumerate(scenarios):
                full_headers = {
                    'x-hubspot-ratelimit-secondly': '19',
                    'x-hubspot-ratelimit-max': '190',
                    'x-hubspot-ratelimit-interval-milliseconds': '10000',
                    **headers,
                }
                
                limiter.wait_for_rate_limit(full_headers)
                
                if mock_sleep.call_args:
                    sleep_times.append(mock_sleep.call_args[0][0])
                else:
                    sleep_times.append(0)
                
                mock_sleep.reset_mock()
        
        assert len(sleep_times) == 4
        assert sleep_times[2] > sleep_times[1]
        assert sleep_times[3] > sleep_times[2]
        assert sleep_times[3] == 1.1


@pytest.fixture
def mock_hubspot_headers_normal():
    """Mock headers for normal HubSpot operation."""
    return {
        'x-hubspot-ratelimit-secondly-remaining': '15',
        'x-hubspot-ratelimit-secondly': '19',
        'x-hubspot-ratelimit-remaining': '150',
        'x-hubspot-ratelimit-max': '190',
        'x-hubspot-ratelimit-interval-milliseconds': '10000',
    }


@pytest.fixture
def mock_hubspot_headers_critical():
    """Mock headers for critical rate limit situation."""
    return {
        'x-hubspot-ratelimit-secondly-remaining': '1',
        'x-hubspot-ratelimit-secondly': '19',
        'x-hubspot-ratelimit-remaining': '5',
        'x-hubspot-ratelimit-max': '190',
        'x-hubspot-ratelimit-interval-milliseconds': '10000',
    }


@pytest.fixture
def mock_hubspot_response():
    """Mock HubSpot API response with headers."""
    class MockResponse:
        def __init__(self, headers):
            self.headers = headers
    
    return MockResponse
