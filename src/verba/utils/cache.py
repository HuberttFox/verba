"""Thread-safe TTL cache with LRU-style eviction."""

from __future__ import annotations

import time
from collections import OrderedDict
from threading import Lock
from typing import Generic, TypeVar

T = TypeVar("T")


class TTLCache(Generic[T]):
    """Key -> value cache; entries expire after ``ttl_seconds``.

    When full, the least recently used entry is evicted.
    """

    def __init__(self, ttl_seconds: float = 3600.0, max_entries: int = 1024) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._data: OrderedDict[str, tuple[float, T]] = OrderedDict()
        self._lock = Lock()

    def get(self, key: str) -> T | None:
        with self._lock:
            item = self._data.get(key)
            if item is None:
                return None
            expires_at, value = item
            if time.monotonic() > expires_at:
                del self._data[key]
                return None
            self._data.move_to_end(key)
            return value

    def set(self, key: str, value: T, ttl_seconds: float | None = None) -> None:
        with self._lock:
            self._data[key] = (
                time.monotonic() + (ttl_seconds or self.ttl_seconds),
                value,
            )
            self._data.move_to_end(key)
            while len(self._data) > self.max_entries:
                self._data.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)
