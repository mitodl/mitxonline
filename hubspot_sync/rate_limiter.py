"""
Rate limiting for HubSpot API calls
"""

import logging
import time

from django.conf import settings

log = logging.getLogger(__name__)

CRITICAL_SECONDLY_THRESHOLD = 2
WARNING_SECONDLY_THRESHOLD = 5
CRITICAL_INTERVAL_THRESHOLD = 10


class HubSpotRateLimiter:
    """
    A rate limiter that adapts to HubSpot's API rate limits by parsing
    response headers and adding delays.
    """

    def __init__(self):
        self.last_request_time = 0
        self.min_delay_ms = getattr(settings, "HUBSPOT_TASK_DELAY", 60)

    def wait_for_rate_limit(self, response_headers: dict | None = None) -> None:
        """
        Wait for an amount of time based on rate limit headers in the response.

        Args:
            response_headers: HTTP response headers from HubSpot API response
        """
        current_time = time.time()

        if response_headers:
            delay_ms = self._calculate_delay_from_headers(response_headers)
        else:
            delay_ms = self.min_delay_ms

        time_since_last = (current_time - self.last_request_time) * 1000
        if time_since_last < delay_ms:
            sleep_time = (delay_ms - time_since_last) / 1000
            log.debug("Rate limiting: sleeping for %.3f seconds", sleep_time)
            time.sleep(sleep_time)

        self.last_request_time = time.time()

    def _calculate_delay_from_headers(self, headers: dict) -> int:
        """
        Calculate delay based on HubSpot rate limit headers.

        Args:
            headers: HTTP response headers from HubSpot

        Returns:
            int: Delay in milliseconds
        """
        try:
            # Check if we're close to hitting limits
            remaining_secondly = int(
                headers.get("x-hubspot-ratelimit-secondly-remaining", 19)
            )
            max_secondly = int(headers.get("x-hubspot-ratelimit-secondly", 19))

            remaining_interval = int(headers.get("x-hubspot-ratelimit-remaining", 190))
            max_interval = int(headers.get("x-hubspot-ratelimit-max", 190))
            interval_ms = int(
                headers.get("x-hubspot-ratelimit-interval-milliseconds", 10000)
            )

            if remaining_secondly <= CRITICAL_SECONDLY_THRESHOLD:
                return 1100
            elif remaining_secondly <= WARNING_SECONDLY_THRESHOLD:
                return 250
            elif remaining_interval <= CRITICAL_INTERVAL_THRESHOLD:
                return max(200, interval_ms // max_interval * 2)
            else:
                target_rate = min(
                    max_secondly * 0.8, max_interval * 0.8 / (interval_ms / 1000)
                )
                return int(1000 / target_rate) if target_rate > 0 else self.min_delay_ms

        except (ValueError, KeyError, ZeroDivisionError) as e:
            log.warning("Failed to parse rate limit headers: %s", str(e))
            return self.min_delay_ms


rate_limiter = HubSpotRateLimiter()


def wait_for_hubspot_rate_limit(response_headers: dict | None = None) -> None:
    """
    Wait for HubSpot rate limits.

    Args:
        response_headers: Optional HTTP response headers from HubSpot API
    """
    rate_limiter.wait_for_rate_limit(response_headers)


def calculate_exponential_backoff(attempt: int, base_delay: int = 60) -> float:
    """
    Exponential backoff delay for retries.

    Args:
        attempt: Current retry attempt (0-based)
        base_delay: Base delay in seconds

    Returns:
        float: Delay in seconds
    """
    max_delay = 300
    return min(base_delay * (2**attempt), max_delay)
