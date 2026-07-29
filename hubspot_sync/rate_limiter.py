"""
Rate limiting for HubSpot API calls
"""

import logging
import random
import time
import uuid

from django.conf import settings

log = logging.getLogger(__name__)

# Atomic sliding-window rate limiter implemented as a Redis Lua script.
#
# The sorted set stores claimed slots: member = unique ID, score = scheduled
# execution time. Cleanup removes slots whose window has expired. When all
# slots in the current window are claimed, the next slot is pushed past the
# oldest slot's window boundary, distributing load across workers automatically.
_RATE_LIMIT_LUA = """
local key       = KEYS[1]
local now       = tonumber(ARGV[1])
local window    = tonumber(ARGV[2])
local max_req   = tonumber(ARGV[3])
local min_delay = tonumber(ARGV[4])
local member    = ARGV[5]

redis.call('ZREMRANGEBYSCORE', key, '-inf', now - window)

local count = redis.call('ZCARD', key)
local target

if count < max_req then
    if count > 0 then
        local last   = redis.call('ZRANGE', key, -1, -1, 'WITHSCORES')
        local last_t = tonumber(last[2])
        target = math.max(now, last_t + min_delay)
    else
        target = now
    end
else
    local oldest   = redis.call('ZRANGE', key,  0,  0, 'WITHSCORES')
    local last     = redis.call('ZRANGE', key, -1, -1, 'WITHSCORES')
    local oldest_t = tonumber(oldest[2])
    local last_t   = tonumber(last[2])
    target = math.max(oldest_t + window, last_t + min_delay, now)
end

redis.call('ZADD', key, target, member)
redis.call('EXPIRE', key, math.ceil(window) + 1)

local wait_ms = (target - now) * 1000
if wait_ms < 0 then wait_ms = 0 end
return tostring(wait_ms)
"""


class HubSpotRateLimiter:
    """
    Distributed rate limiter using a Redis sorted-set sliding window.

    All Celery workers share the same Redis key, so rate limiting is enforced
    globally across processes rather than per-process.
    """

    def __init__(self):
        self.min_delay_ms = getattr(settings, "HUBSPOT_TASK_DELAY", 60)
        self._window_size_seconds = 1.0
        self._max_requests_per_second = 19
        self._redis_key = "hubspot:rate_limit"

    def _get_redis(self):
        from django_redis import get_redis_connection  # noqa: PLC0415

        return get_redis_connection("redis")

    def wait_for_rate_limit(self) -> None:
        redis_client = self._get_redis()
        now = time.time()
        member = str(uuid.uuid4())

        script = redis_client.register_script(_RATE_LIMIT_LUA)
        result = script(
            keys=[self._redis_key],
            args=[
                str(now),
                str(self._window_size_seconds),
                str(self._max_requests_per_second),
                str(self.min_delay_ms / 1000),
                member,
            ],
        )
        wait_ms = float(result)

        if wait_ms > 0:
            sleep_time = wait_ms / 1000
            jitter = random.uniform(-0.05, 0.05) * sleep_time  # noqa: S311
            sleep_time = max(0, sleep_time + jitter)
            log.debug("Rate limiting: sleeping for %.3f seconds", sleep_time)
            time.sleep(sleep_time)


rate_limiter = HubSpotRateLimiter()


def wait_for_hubspot_rate_limit() -> None:
    """
    Wait for HubSpot rate limits.
    """
    rate_limiter.wait_for_rate_limit()
