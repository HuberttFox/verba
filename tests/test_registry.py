from __future__ import annotations

import pytest

from verba.core.registry import (
    DuplicateProviderError,
    ProviderNotFoundError,
    ServiceRegistry,
)


def test_register_get() -> None:
    reg: ServiceRegistry[int] = ServiceRegistry()
    reg.register("a", 1)
    assert reg.get("a") == 1
    assert reg.names() == ["a"]


def test_duplicate_raises() -> None:
    reg: ServiceRegistry[int] = ServiceRegistry()
    reg.register("a", 1)
    with pytest.raises(DuplicateProviderError):
        reg.register("a", 2)
    reg.register("a", 2, replace=True)
    assert reg.get("a") == 2


def test_missing_raises() -> None:
    reg: ServiceRegistry[int] = ServiceRegistry()
    with pytest.raises(ProviderNotFoundError):
        reg.get("nope")
    assert reg.get_or_none("nope") is None


def test_find_predicate() -> None:
    reg: ServiceRegistry[int] = ServiceRegistry()
    reg.register("even", 4)
    reg.register("odd", 3)
    found = reg.find(lambda v: v % 2 == 0)
    assert found == [("even", 4)]
