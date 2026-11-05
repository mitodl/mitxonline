"""Tests for hubspot_sync.rate_limiter"""

from unittest.mock import patch

import pytest
from django.test import override_settings

from hubspot_sync.rate_limiter import (
    _RATE_LIMIT_LUA,
    HubSpotRateLimiter,
)


class TestHubSpotRateLimiter:
    def setup_method(self):
        self.rate_limiter = HubSpotRateLimiter()

    def _mock_redis(self, mocker, wait_ms_bytes=b"0.0"):
        mock_redis = mocker.Mock()
        mock_script = mocker.Mock(return_value=wait_ms_bytes)
        mock_redis.register_script.return_value = mock_script
        mocker.patch.object(self.rate_limiter, "_get_redis", return_value=mock_redis)
        return mock_redis, mock_script

    @override_settings(HUBSPOT_TASK_DELAY=100)
    def test_init_with_custom_delay(self):
        limiter = HubSpotRateLimiter()
        assert limiter.min_delay_ms == 100

    def test_init_sets_correct_defaults(self):
        assert self.rate_limiter.min_delay_ms == 60

    @patch("hubspot_sync.rate_limiter.time.sleep")
    def test_no_sleep_when_redis_returns_zero(self, mock_sleep, mocker):
        self._mock_redis(mocker, b"0.0")
        self.rate_limiter.wait_for_rate_limit()
        mock_sleep.assert_not_called()

    @patch("hubspot_sync.rate_limiter.time.sleep")
    def test_sleeps_when_redis_returns_wait_time(self, mock_sleep, mocker):
        self._mock_redis(mocker, b"500.0")
        self.rate_limiter.wait_for_rate_limit()
        mock_sleep.assert_called_once()
        assert abs(mock_sleep.call_args[0][0] - 0.5) < 0.1

    def test_uses_correct_lua_script(self, mocker):
        mock_redis, _ = self._mock_redis(mocker)
        self.rate_limiter.wait_for_rate_limit()
        mock_redis.register_script.assert_called_once_with(_RATE_LIMIT_LUA)

    def test_script_receives_correct_keys_and_args(self, mocker):
        _, mock_script = self._mock_redis(mocker)
        self.rate_limiter.wait_for_rate_limit()
        call_kwargs = mock_script.call_args[1]
        assert call_kwargs["keys"] == ["hubspot:rate_limit"]
        args = call_kwargs["args"]
        assert args[1] == "1.0"  # window_size_seconds
        assert args[2] == "19"  # max_requests_per_second

    @pytest.mark.parametrize("wait_ms_bytes", [b"0.0", b"100.0", b"999.9"])
    @patch("hubspot_sync.rate_limiter.time.sleep")
    def test_parses_bytes_return_value(self, mock_sleep, wait_ms_bytes, mocker):
        self._mock_redis(mocker, wait_ms_bytes)
        self.rate_limiter.wait_for_rate_limit()
        expected_wait_s = float(wait_ms_bytes) / 1000
        if expected_wait_s > 0:
            assert mock_sleep.called
            assert abs(mock_sleep.call_args[0][0] - expected_wait_s) < 0.1
        else:
            mock_sleep.assert_not_called()

    @patch("hubspot_sync.rate_limiter.log.debug")
    def test_logs_sleep_time_when_rate_limited(self, mock_log, mocker):
        self._mock_redis(mocker, b"200.0")
        self.rate_limiter.wait_for_rate_limit()
        mock_log.assert_called_once()
        assert "Rate limiting: sleeping for" in mock_log.call_args[0][0]
