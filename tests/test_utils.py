from __future__ import annotations

import pytest

from verba.utils.cache import TTLCache
from verba.utils.rate_limit import RateLimiter
from verba.utils.retry import RetryExhausted, RetryPolicy


class FlakyError(Exception):
    pass


def test_rate_limiter_burst_and_throttle() -> None:
    limiter = RateLimiter(rate_per_minute=120, burst=2)
    assert limiter.acquire() is True
    assert limiter.acquire() is True
    assert limiter.acquire() is False


def test_rate_limiter_wait_timeout() -> None:
    limiter = RateLimiter(rate_per_minute=1, burst=1)
    assert limiter.acquire() is True
    assert limiter.wait(timeout=0.05) is False


def test_retry_succeeds_after_failures() -> None:
    calls = 0

    def flaky() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise FlakyError("temp")
        return "ok"

    policy = RetryPolicy(max_attempts=3, base_delay=0.0, retry_on=(FlakyError,))
    assert policy.execute(flaky) == "ok"
    assert calls == 3


def test_retry_exhausted() -> None:
    def always_fail() -> None:
        raise FlakyError("nope")

    policy = RetryPolicy(max_attempts=2, base_delay=0.0, retry_on=(FlakyError,))
    with pytest.raises(RetryExhausted):
        policy.execute(always_fail)


def test_retry_ignores_unmatched_exception() -> None:
    def bad() -> None:
        raise ValueError("not retryable")

    policy = RetryPolicy(max_attempts=3, base_delay=0.0, retry_on=(FlakyError,))
    with pytest.raises(ValueError):
        policy.execute(bad)


def test_ttl_cache_expiry() -> None:
    cache: TTLCache[str] = TTLCache(ttl_seconds=3600)
    cache.set("k", "v", ttl_seconds=0.01)
    assert cache.get("k") is not None
    import time

    time.sleep(0.02)
    assert cache.get("k") is None


def test_ttl_cache_max_entries() -> None:
    cache: TTLCache[int] = TTLCache(max_entries=2)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)
    assert len(cache) == 2
    assert cache.get("a") is None
