"""Tests for ``investo.sources._registry``.

Pins the registration mechanism per
``aidlc-docs/construction/u1-sources/functional-design/domain-entities.md``
§E2 and ``business-logic-model.md`` L3 and ``business-rules.md`` R2.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import ClassVar

import httpx
import pytest

from investo.models import Category, NormalizedItem
from investo.sources._registry import (
    _ADAPTERS,
    _clear_for_test,
    list_sources,
    register,
)
from investo.sources._window import FetchWindow


@pytest.fixture(autouse=True)
def _isolate_registry() -> Iterator[None]:
    """Snapshot/restore the registry around each test.

    The runtime registry is populated at import time of
    ``investo.sources``; today that's empty (Step 9 will wire adapter
    imports), but the snapshot/restore keeps the test correct once the
    real adapters land.
    """

    snapshot = dict(_ADAPTERS)
    _clear_for_test()
    try:
        yield
    finally:
        _clear_for_test()
        _ADAPTERS.update(snapshot)


# Convenience: a single Protocol-conformant stub used across tests.
# Each test defines a fresh subclass so the registry stays clean.
class _StubBase:
    name: ClassVar[str] = "<override-me>"
    category: ClassVar[Category] = "news"

    async def fetch(
        self,
        client: httpx.AsyncClient,
        window: FetchWindow,
    ) -> list[NormalizedItem]:
        return []


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_register_adds_adapter_to_registry() -> None:
    @register
    class Stub(_StubBase):
        name: ClassVar[str] = "stub-1"

    assert "stub-1" in _ADAPTERS
    assert isinstance(_ADAPTERS["stub-1"], Stub)


def test_register_returns_class_unchanged() -> None:
    @register
    class Stub(_StubBase):
        name: ClassVar[str] = "stub-2"

    # Decorator is transparent — class object, not the instance.
    assert Stub.name == "stub-2"
    assert callable(Stub)


def test_list_sources_returns_singleton_instance() -> None:
    @register
    class Stub(_StubBase):
        name: ClassVar[str] = "stub-3"

    sources = list_sources()
    assert len(sources) == 1
    assert isinstance(sources[0], Stub)
    # Same instance on a second call (singleton per process).
    assert list_sources()[0] is sources[0]


def test_multiple_registers_preserve_insertion_order() -> None:
    @register
    class A(_StubBase):
        name: ClassVar[str] = "a"

    @register
    class B(_StubBase):
        name: ClassVar[str] = "b"

    @register
    class C(_StubBase):
        name: ClassVar[str] = "c"

    assert [s.name for s in list_sources()] == ["a", "b", "c"]


def test_list_sources_empty_initially() -> None:
    # Fixture clears the registry at entry; nothing registered in this test.
    assert list_sources() == []


# ---------------------------------------------------------------------------
# Duplicate-name rejection (FD R2)
# ---------------------------------------------------------------------------


def test_duplicate_name_raises_runtime_error() -> None:
    @register
    class First(_StubBase):
        name: ClassVar[str] = "duplicate"

    with pytest.raises(RuntimeError, match="duplicate source name"):

        @register
        class Second(_StubBase):
            name: ClassVar[str] = "duplicate"
            category: ClassVar[Category] = "macro"  # different category, same name


def test_duplicate_error_message_includes_name() -> None:
    @register
    class First(_StubBase):
        name: ClassVar[str] = "fomc-rss"
        category: ClassVar[Category] = "calendar"

    with pytest.raises(RuntimeError) as exc_info:

        @register
        class Second(_StubBase):
            name: ClassVar[str] = "fomc-rss"

    assert "fomc-rss" in str(exc_info.value)


def test_duplicate_does_not_replace_existing_entry() -> None:
    @register
    class First(_StubBase):
        name: ClassVar[str] = "shared"

    original = _ADAPTERS["shared"]

    with pytest.raises(RuntimeError):

        @register
        class Second(_StubBase):
            name: ClassVar[str] = "shared"
            category: ClassVar[Category] = "macro"

    # Registry still holds the first instance.
    assert _ADAPTERS["shared"] is original


# ---------------------------------------------------------------------------
# Return-value mutation safety (FD §E2: "the registry is never mutated")
# ---------------------------------------------------------------------------


def test_list_sources_mutation_does_not_affect_registry() -> None:
    @register
    class Stub(_StubBase):
        name: ClassVar[str] = "alpha"

    sources = list_sources()
    sources.clear()
    sources.append("not an adapter")  # type: ignore[arg-type]

    fresh = list_sources()
    assert len(fresh) == 1
    assert fresh[0].name == "alpha"


def test_list_sources_returns_a_fresh_list_each_call() -> None:
    @register
    class Stub(_StubBase):
        name: ClassVar[str] = "beta"

    a = list_sources()
    b = list_sources()
    assert a is not b
    # But the singleton instances inside are the same.
    assert a[0] is b[0]


# ---------------------------------------------------------------------------
# _clear_for_test utility
# ---------------------------------------------------------------------------


def test_clear_for_test_empties_registry() -> None:
    @register
    class Stub(_StubBase):
        name: ClassVar[str] = "to-clear"

    assert len(list_sources()) == 1
    _clear_for_test()
    assert list_sources() == []


def test_clear_for_test_allows_re_registration() -> None:
    @register
    class First(_StubBase):
        name: ClassVar[str] = "recyclable"

    _clear_for_test()

    # After clearing, the same name can be registered again — the test
    # fixture pattern relies on this being safe.
    @register
    class Second(_StubBase):
        name: ClassVar[str] = "recyclable"

    assert "recyclable" in _ADAPTERS
    assert isinstance(_ADAPTERS["recyclable"], Second)
