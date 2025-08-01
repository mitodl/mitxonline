"""
Rate limiting for HubSpot API calls
"""

import logging
import random
import threading
import time
from collections import deque

from django.conf import settings

log = logging.getLogger(__name__)


class HubSpotRateLimiter:
    """
    A scalable rate limiter that uses a sliding window approach to handle
    thousands of concurrent requests efficiently.
    """

    def __init__(self):
        self.min_delay_ms = getattr(settings, "HUBSPOT_TASK_DELAY", 60)

        # Sliding window approach - track recent request timestamps
        self._lock = threading.Lock()
        self._request_times = deque()

        # Rate limiting parameters
        self._window_size_seconds = 1.0  # 1 second sliding window
        self._max_requests_per_second = 1000 / self.min_delay_ms  # Derived from min_delay

        # Performance optimization: batch cleanup every N requests
        self._cleanup_counter = 0
        self._cleanup_interval = 50

    def wait_for_rate_limit(self) -> None:
        """
        Wait for an amount of time based on sliding window rate limiting.
        This scales efficiently to thousands of concurrent requests.
        """
        current_time = time.time()
        
        with self._lock:
            # Periodically clean old timestamps for performance
            self._cleanup_counter += 1
            if self._cleanup_counter >= self._cleanup_interval:
                self._cleanup_old_timestamps(current_time)
                self._cleanup_counter = 0

            # Calculate when this request can proceed
            target_time = self._calculate_next_available_time(current_time)

            # Add this request to the window
            self._request_times.append(target_time)

            # Calculate sleep time
            sleep_time = max(0, target_time - current_time)

        if sleep_time > 0:
            # Add jitter to prevent thundering herd (±5% of sleep time)
            jitter = random.uniform(-0.05, 0.05) * sleep_time  # noqa: S311
            sleep_time = max(0, sleep_time + jitter)

            log.debug("Rate limiting: sleeping for %.3f seconds", sleep_time)
            time.sleep(sleep_time)

    def _cleanup_old_timestamps(self, current_time: float) -> None:
        """Remove timestamps outside the sliding window."""
        cutoff_time = current_time - self._window_size_seconds
        while self._request_times and self._request_times[0] < cutoff_time:
            self._request_times.popleft()

    def _calculate_next_available_time(self, current_time: float) -> float:
        """
        Calculate when the next request can be made based on the sliding window.
        """
        # Clean old timestamps first
        self._cleanup_old_timestamps(current_time)

        # If we're under the rate limit, request can proceed immediately
        if len(self._request_times) < self._max_requests_per_second:
            # Still enforce minimum delay from the last request
            if self._request_times:
                last_request_time = self._request_times[-1]
                min_next_time = last_request_time + (self.min_delay_ms / 1000)
                return max(current_time, min_next_time)
            return current_time

        # We're at the rate limit - find when the oldest request in window expires
        oldest_in_window = self._request_times[0]
        next_available = oldest_in_window + self._window_size_seconds

        # Ensure we still respect minimum delay
        if self._request_times:
            last_request_time = self._request_times[-1]
            min_next_time = last_request_time + (self.min_delay_ms / 1000)
            next_available = max(next_available, min_next_time)

        return max(next_available, current_time)

    def get_current_load(self) -> dict:
        """Get current rate limiter statistics for monitoring."""
        with self._lock:
            current_time = time.time()
            self._cleanup_old_timestamps(current_time)

            return {
                "requests_in_window": len(self._request_times),
                "max_requests_per_second": self._max_requests_per_second,
                "utilization_percent": (len(self._request_times) / self._max_requests_per_second) * 100,
                "window_size_seconds": self._window_size_seconds,
            }


rate_limiter = HubSpotRateLimiter()


def wait_for_hubspot_rate_limit() -> None:
    """
    Wait for HubSpot rate limits.
    """
    rate_limiter.wait_for_rate_limit()
