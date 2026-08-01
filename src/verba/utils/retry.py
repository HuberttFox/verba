"""Exponential-backoff retry policy for flaky provider calls."""

from __future__ import annotations

import time
from typing import Callable, TypeVar

T = TypeVar("T")


class RetryExhausted(Exception):
    """Raised when all attempts failed."""


class RetryPolicy:
    """Retries *fn* with exponential backoff on matching exceptions.

    Usage::

        policy = RetryPolicy(max_attempts=3)
        result = policy.execute(lambda: provider.translate(request))
    """

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 0.5,
        max_delay: float = 30.0,
        backoff_factor: float = 2.0,
        retry_on: tuple[type[Exception], ...] | None = None,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.retry_on = retry_on or (Exception,)

    def execute(self, fn: Callable[[], T]) -> T:
        """Call *fn*, retrying on retryable exceptions, then raise RetryExhausted."""
        delay = self.base_delay
        for attempt in range(1, self.max_attempts + 1):
            try:
                return fn()
            except self.retry_on:
                if attempt == self.max_attempts:
                    raise RetryExhausted(
                        f"failed after {attempt} attempt(s)"
                    ) from None
                time.sleep(delay)
                delay = min(delay * self.backoff_factor, self.max_delay)
        raise RetryExhausted("unreachable")
