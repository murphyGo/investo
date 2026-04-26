"""Tests for ``investo.sources.protocol``.

Pins the public adapter contract per
``aidlc-docs/construction/u1-sources/functional-design/domain-entities.md``
§E1 (SourceAdapter Protocol) and §E4 (SourceFetchError).
"""

from __future__ import annotations

from datetime import date
from typing import ClassVar

import httpx

from investo.models import Category, NormalizedItem
from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceAdapter, SourceFetchError

# ---------------------------------------------------------------------------
# SourceFetchError contract (§E4)
# ---------------------------------------------------------------------------


def test_source_fetch_error_is_exception_subclass() -> None:
    err = SourceFetchError("test", "msg", transient=True)
    assert isinstance(err, Exception)


def test_source_fetch_error_is_not_runtime_error_subclass() -> None:
    # Per FD §E4 — subclass of Exception, NOT RuntimeError, so callers
    # can pytest.raises(SourceFetchError) without catching unrelated
    # programmer-error RuntimeErrors.
    err = SourceFetchError("test", "msg", transient=True)
    assert not isinstance(err, RuntimeError)


def test_source_fetch_error_attributes_present() -> None:
    cause = ValueError("boom")
    err = SourceFetchError("fomc-rss", "kaboom", transient=True, cause=cause)
    assert err.source_name == "fomc-rss"
    assert err.transient is True
    assert err.cause is cause


def test_source_fetch_error_cause_optional() -> None:
    err = SourceFetchError("fomc-rss", "kaboom", transient=False)
    assert err.cause is None


def test_source_fetch_error_message_contains_source_and_text() -> None:
    err = SourceFetchError("fomc-rss", "boom", transient=True)
    rendered = str(err)
    assert "fomc-rss" in rendered
    assert "boom" in rendered


def test_source_fetch_error_from_chain_preserves_cause() -> None:
    inner = ValueError("XML decode failed")
    try:
        try:
            raise inner
        except ValueError as exc:
            raise SourceFetchError("test", "wrap", transient=False, cause=exc) from exc
    except SourceFetchError as err:
        assert err.__cause__ is inner
        assert err.cause is inner


def test_source_fetch_error_accepts_base_exception_cause() -> None:
    # FD §E4 types `cause` as `BaseException | None` — covers
    # SystemExit / KeyboardInterrupt even though they would not
    # normally be wrapped in production code.
    cause = SystemExit(1)
    err = SourceFetchError("test", "msg", transient=False, cause=cause)
    assert err.cause is cause


def test_source_fetch_error_re_exported_from_retry() -> None:
    # Step 5 relocation: protocol.py is the canonical home; _retry.py
    # re-imports for backward compatibility with prior test imports.
    from investo.sources._retry import SourceFetchError as ReExported

    assert ReExported is SourceFetchError


# ---------------------------------------------------------------------------
# SourceAdapter Protocol shape (§E1)
# ---------------------------------------------------------------------------


def test_source_adapter_is_a_protocol() -> None:
    # `_is_protocol` is the de-facto-public CPython introspection hook
    # for Protocol classes (stable since 3.8). Sharper than walking
    # __mro__ because it directly answers "is this a Protocol?".
    assert getattr(SourceAdapter, "_is_protocol", False) is True


def test_source_adapter_is_not_runtime_checkable() -> None:
    # Pinned behavior: SourceAdapter is NOT @runtime_checkable. The
    # registry uses class-attribute inspection at registration time
    # rather than isinstance checks, so making this runtime-checkable
    # would just invite false-positive duck-typed matches elsewhere.
    # `_is_runtime_protocol` is the documented marker `@runtime_checkable`
    # sets — a direct pin that doesn't go through isinstance side-effects.
    assert getattr(SourceAdapter, "_is_runtime_protocol", False) is False


def test_source_adapter_declares_name_and_category() -> None:
    annotations = SourceAdapter.__annotations__
    assert "name" in annotations
    assert "category" in annotations


# ---------------------------------------------------------------------------
# A concrete stub adapter satisfies the Protocol (mypy proof + runtime probe)
# ---------------------------------------------------------------------------


class _StubAdapter:
    """Minimal Protocol-satisfying adapter used only by these tests."""

    name: ClassVar[str] = "stub"
    category: ClassVar[Category] = "news"

    async def fetch(
        self,
        client: httpx.AsyncClient,
        window: FetchWindow,
    ) -> list[NormalizedItem]:
        return []


def test_stub_adapter_assignable_to_protocol_typed_binding() -> None:
    # mypy strict at type-check time validates the structural match;
    # the runtime assertion just confirms the assignment doesn't raise.
    adapter: SourceAdapter = _StubAdapter()
    assert adapter.name == "stub"
    assert adapter.category == "news"


async def test_stub_adapter_fetch_returns_list() -> None:
    adapter: SourceAdapter = _StubAdapter()
    async with httpx.AsyncClient() as client:
        window = FetchWindow.from_kst_date(date(2026, 4, 27))
        result = await adapter.fetch(client, window)
    assert result == []
