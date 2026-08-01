"""Typed service registry: name-based lookup of provider instances."""

from __future__ import annotations

from threading import Lock
from typing import Callable, Generic, TypeVar

T = TypeVar("T")


class DuplicateProviderError(KeyError):
    """Raised when registering a provider name that already exists."""


class ProviderNotFoundError(KeyError):
    """Raised when requesting a provider name that is not registered."""


class ServiceRegistry(Generic[T]):
    """Holds instances of one provider kind (translators, OCR, ...).

    Thread-safe: registration and lookup may happen from any thread.
    """

    def __init__(self) -> None:
        self._items: dict[str, T] = {}
        self._lock = Lock()

    def register(self, name: str, provider: T, *, replace: bool = False) -> None:
        with self._lock:
            if name in self._items and not replace:
                raise DuplicateProviderError(name)
            self._items[name] = provider

    def unregister(self, name: str) -> None:
        with self._lock:
            self._items.pop(name, None)

    def get(self, name: str) -> T:
        with self._lock:
            provider = self._items.get(name)
        if provider is None:
            raise ProviderNotFoundError(name)
        return provider

    def get_or_none(self, name: str) -> T | None:
        with self._lock:
            return self._items.get(name)

    def names(self) -> list[str]:
        with self._lock:
            return list(self._items)

    def find(self, predicate: Callable[[T], bool]) -> list[tuple[str, T]]:
        with self._lock:
            return [(n, p) for n, p in self._items.items() if predicate(p)]

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)
