"""Tests for ``investo.sources.dart_disclosure.DartDisclosureAdapter``.

Pins u41 plan DoD + R10 (real fixtures) + R13 (secret hygiene):

* Real recorded OpenDART list.json fixtures (live API, key redacted from
  the URL only — JSON bodies do not echo the key).
* AC-3.6 / R13 — missing/empty ``OPENDART_API_KEY`` →
  ``SourceFetchError(transient=False)``; key value never in error
  messages or ``raw_metadata``.
* Subcategory mapping covers all 4 plan categories (buyback / dividend /
  capital_change / ownership_change).
* Status code handling — ``000`` ok, ``013`` empty, ``010`` terminal.
* Window filter (R7 strict) — items outside the KST trading-day window
  are dropped.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest

from investo.sources._window import FetchWindow
from investo.sources.dart_disclosure import DartDisclosureAdapter
from investo.sources.protocol import SourceFetchError
from investo.sources.tiers import adapter_tier

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "api" / "dart-disclosure"

# Sentinel api_key value used in tests. Tests assert this string never
# appears in any captured output (errors, raw_metadata, etc.).
_SENTINEL_KEY = "REDACTED_OPENDART_KEY_DO_NOT_LEAK_0123456789"


def _client_for(
    fixture_name: str, *, status: int = 200
) -> tuple[httpx.AsyncClient, list[httpx.Request]]:
    """Mock client returning a single fixture body for any request."""
    body = (_FIXTURE_DIR / fixture_name).read_bytes()
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            status,
            content=body,
            headers={"content-type": "application/json"},
        )

    return httpx.AsyncClient(transport=httpx.MockTransport(handler)), captured


def _set_key(monkeypatch: pytest.MonkeyPatch, value: str = _SENTINEL_KEY) -> None:
    monkeypatch.setenv("OPENDART_API_KEY", value)


# ---------------------------------------------------------------------------
# AC-3.6 / R13 — missing-secret graceful degradation
# ---------------------------------------------------------------------------


async def test_missing_opendart_api_key_raises_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENDART_API_KEY", raising=False)
    adapter = DartDisclosureAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 8))
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(500))
    ) as client:
        with pytest.raises(SourceFetchError) as exc_info:
            await adapter.fetch(client, window)
    err = exc_info.value
    assert err.transient is False
    assert err.source_name == "dart-disclosure"
    assert err.cause is None
    # Error message names the env var, not any key value.
    assert "OPENDART_API_KEY" in str(err)
    assert "dart-disclosure" in str(err)


async def test_empty_opendart_api_key_raises_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENDART_API_KEY", "")
    adapter = DartDisclosureAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 8))
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(500))
    ) as client:
        with pytest.raises(SourceFetchError) as exc_info:
            await adapter.fetch(client, window)
    assert exc_info.value.transient is False


async def test_missing_key_does_not_attempt_any_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENDART_API_KEY", raising=False)
    requests_seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests_seen.append(request)
        return httpx.Response(200, json={})

    adapter = DartDisclosureAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 8))
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(SourceFetchError):
            await adapter.fetch(client, window)
    assert requests_seen == []


# ---------------------------------------------------------------------------
# Secret hygiene — sentinel key never leaks into items / errors
# ---------------------------------------------------------------------------


async def test_api_key_not_in_raw_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_key(monkeypatch)
    client, _ = _client_for("recent_all.json")
    adapter = DartDisclosureAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 8))
    async with client:
        items = await adapter.fetch(client, window)
    assert items, "fixture should yield at least one normalized item"
    for item in items:
        for k, v in item.raw_metadata.items():
            assert _SENTINEL_KEY not in k
            assert _SENTINEL_KEY not in str(v)


async def test_api_key_in_url_but_not_in_unknown_status_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The crtfc_key WAS sent in the URL (DART requires it) but errors
    must not echo it."""
    _set_key(monkeypatch)
    # Construct a status=999 response (unknown code) to force the
    # defense-in-depth branch.
    body = json.dumps({"status": "999", "message": "weird condition"}).encode("utf-8")

    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, content=body, headers={"content-type": "application/json"})

    adapter = DartDisclosureAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 8))
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(SourceFetchError) as exc_info:
            await adapter.fetch(client, window)
    # crtfc_key was sent in the URL.
    assert captured[0].url.params["crtfc_key"] == _SENTINEL_KEY
    # But never echoed in the error message.
    msg_blob = str(exc_info.value) + repr(exc_info.value)
    assert _SENTINEL_KEY not in msg_blob


# ---------------------------------------------------------------------------
# Status code handling
# ---------------------------------------------------------------------------


async def test_status_013_empty_returns_empty_list(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_key(monkeypatch)
    client, _ = _client_for("empty.json")
    adapter = DartDisclosureAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 8))
    async with client:
        items = await adapter.fetch(client, window)
    assert items == []


async def test_status_010_invalid_key_raises_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_key(monkeypatch)
    client, _ = _client_for("invalid_key.json")
    adapter = DartDisclosureAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 8))
    async with client:
        with pytest.raises(SourceFetchError) as exc_info:
            await adapter.fetch(client, window)
    err = exc_info.value
    assert err.transient is False
    assert "010" in str(err)
    # The key value never leaks into the error.
    assert _SENTINEL_KEY not in str(err)


async def test_status_020_rate_limit_raises_transient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_key(monkeypatch)
    body = json.dumps({"status": "020", "message": "사용한도 초과"}).encode("utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body, headers={"content-type": "application/json"})

    adapter = DartDisclosureAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 8))
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(SourceFetchError) as exc_info:
            await adapter.fetch(client, window)
    assert exc_info.value.transient is True
    assert "020" in str(exc_info.value)


async def test_status_100_invalid_field_raises_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_key(monkeypatch)
    body = json.dumps({"status": "100", "message": "필드 잘못됨"}).encode("utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body, headers={"content-type": "application/json"})

    adapter = DartDisclosureAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 8))
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(SourceFetchError) as exc_info:
            await adapter.fetch(client, window)
    assert exc_info.value.transient is False


# ---------------------------------------------------------------------------
# Recorded-fixture happy path — 4 categories
# ---------------------------------------------------------------------------


async def test_recent_all_routes_to_three_subcategories(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``recent_all.json`` (2026-05-08 mixed feed) carries buyback,
    capital_change, and ownership_change items. Dividend reports are
    rare in early-May (post-earnings season) — that is exercised in
    the dedicated dividend fixture below.
    """
    _set_key(monkeypatch)
    client, captured = _client_for("recent_all.json")
    adapter = DartDisclosureAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 8))
    async with client:
        items = await adapter.fetch(client, window)
    assert items, "expected at least one normalized item from recent_all.json"
    subcats = {item.raw_metadata["subcategory"] for item in items}
    # Three of the four categories must surface from this fixture.
    assert {"buyback", "capital_change", "ownership_change"} <= subcats

    # Confirm the URL carried the date params we computed.
    assert captured[0].url.params["bgn_de"] == "20260508"
    assert captured[0].url.params["end_de"] == "20260508"

    # Spot-check fields on the first item.
    first = items[0]
    assert first.source_name == "dart-disclosure"
    assert first.category == "news"
    assert first.title.startswith("[DART] ")
    assert first.url is not None
    assert str(first.url).startswith("https://dart.fss.or.kr/dsaf001/main.do?rcpNo=")
    assert "rcept_no" in first.raw_metadata
    assert "corp_code" in first.raw_metadata
    assert "corp_name" in first.raw_metadata
    assert "subcategory" in first.raw_metadata
    # rcept_dt round-trip → 2026-05-08 09:00 KST → 2026-05-08 00:00 UTC
    assert first.published_at == datetime(2026, 5, 8, 0, 0, tzinfo=UTC)


async def test_treasury_stock_fixture_yields_buyback_subcat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_key(monkeypatch)
    client, _ = _client_for("treasury_stock.json")
    adapter = DartDisclosureAdapter()
    # Fixture spans 5/6, 5/7, 5/8 — pick 5/8 to keep window strict.
    window = FetchWindow.from_kst_date(date(2026, 5, 8))
    async with client:
        items = await adapter.fetch(client, window)
    assert items
    subcats = {it.raw_metadata["subcategory"] for it in items}
    assert "buyback" in subcats


async def test_dividend_fixture_yields_dividend_subcat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_key(monkeypatch)
    client, _ = _client_for("dividend.json")
    adapter = DartDisclosureAdapter()
    # dividend.json spans 2026-03-03 ~ 2026-03-13. The 2026-03-05 slice
    # is the one with an actual ``현금ㆍ현물배당결정`` report (the 3/13
    # slice happens to be heavy with prospectus filings that match the
    # ``배당`` keyword by name only — the dividend fixture exists to
    # exercise the keyword path on a real declaration).
    window = FetchWindow.from_kst_date(date(2026, 3, 5))
    async with client:
        items = await adapter.fetch(client, window)
    assert items
    subcats = {it.raw_metadata["subcategory"] for it in items}
    assert "dividend" in subcats


async def test_capital_fixture_yields_capital_change_subcat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_key(monkeypatch)
    client, _ = _client_for("capital.json")
    adapter = DartDisclosureAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 8))
    async with client:
        items = await adapter.fetch(client, window)
    assert items
    subcats = {it.raw_metadata["subcategory"] for it in items}
    assert "capital_change" in subcats


async def test_major_holder_fixture_yields_ownership_change_subcat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_key(monkeypatch)
    client, _ = _client_for("major_holder.json")
    adapter = DartDisclosureAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 8))
    async with client:
        items = await adapter.fetch(client, window)
    assert items
    subcats = {it.raw_metadata["subcategory"] for it in items}
    assert "ownership_change" in subcats


# ---------------------------------------------------------------------------
# Window filter (R7 strict)
# ---------------------------------------------------------------------------


async def test_items_outside_kst_window_are_dropped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Window points to 2026-05-07 KST but fixture is all 2026-05-08
    items — every item must be filtered out by ``window.contains``.
    """
    _set_key(monkeypatch)
    client, _ = _client_for("recent_all.json")
    adapter = DartDisclosureAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 7))
    async with client:
        items = await adapter.fetch(client, window)
    assert items == []


# ---------------------------------------------------------------------------
# Subcategory keyword classifier
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("report_nm", "expected"),
    [
        ("주요사항보고서(자기주식취득결정)", "buyback"),
        ("주요사항보고서(자기주식처분결정)", "buyback"),
        ("자사주취득신탁계약체결", "buyback"),
        ("[첨부추가]현금ㆍ현물배당결정", "dividend"),
        ("주식배당결정", "dividend"),
        ("주요사항보고서(유상증자결정)", "capital_change"),
        ("[기재정정]주요사항보고서(전환사채권발행결정)", "capital_change"),
        ("주요사항보고서(감자결정)", "capital_change"),
        ("주요사항보고서(신주인수권부사채권발행결정)", "capital_change"),
        ("최대주주변경", "ownership_change"),
        ("주식등의대량보유상황보고서(일반)", "ownership_change"),
        ("임원ㆍ주요주주특정증권등소유상황보고서", "ownership_change"),
        # Off-topic reports — must drop (return None).
        ("분기보고서 (2026.03)", None),
        ("감사보고서 (2025.12)", None),
        ("증권발행실적보고서", None),
    ],
)
def test_classify_subcategory_keywords(report_nm: str, expected: str | None) -> None:
    assert DartDisclosureAdapter._classify(report_nm) == expected


# ---------------------------------------------------------------------------
# Class identity + tier registry
# ---------------------------------------------------------------------------


def test_class_attributes() -> None:
    assert DartDisclosureAdapter.name == "dart-disclosure"
    assert DartDisclosureAdapter.category == "news"


def test_tier_registry_pins_dart_disclosure_to_s() -> None:
    assert adapter_tier("dart-disclosure") == "S"
