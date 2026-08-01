"""Thread-safe token-bucket rate limiter for provider calls."""

from __future__ import annotations

import time
from threading import Lock


class RateLimiter:
    """Token bucket. ``wait()`` blocks until a token is available.

    Example: 10 requests/min, burst of 2 -> two quick calls, then ~6s each.
    """

    def __init__(self, rate_per_minute: float, burst: int = 1) -> None:
        if rate_per_minute <= 0:
            raise ValueError("rate_per_minute must be positive")
        if burst < 1:
            raise ValueError("burst must be >= 1")
        self._interval = 60.0 / rate_per_minute
        self._burst = burst
        self._tokens = float(burst)
        self._last_refill = time.monotonic()
        self._lock = Lock()

    def acquire(self) -> bool:
        """Try to take a token without blocking."""
        with self._lock:
            self._refill()
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return True
            return False

    def wait(self, timeout: float | None = None) -> bool:
        """Block until a token is available (or *timeout* seconds elapse)."""
        deadline = None if timeout is None else time.monotonic() + timeout
        while not self.acquire():
            with self._lock:
                self._refill()
                sleep_for = min(self._interval, 0.05)
            if deadline is not None and time.monotonic() + sleep_for > deadline:
                return False
            time.sleep(sleep_for)
        return True

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._burst, self._tokens + elapsed / self._interval)
        self._last_refill = now
