"""Tests for ``investo.sources.krx_foreign_flows.KrxForeignFlowsAdapter`` (u53).

Pins the algorithm declared in the adapter docstring:

* Recorded Naver finance fixtures replay (``fixtures/api/krx-foreign-flows/``)
  — KOSPI / KOSDAQ across 2 business days, EUC-KR HTML.
* Row selection by ``bizdate`` (target date in KST) with weekend
  fallback to nearest preceding business-day row.
* 4 investor categories per market = 8 ``NormalizedItem`` per successful
  fetch (individual / foreign / institution / other).
* ``raw_metadata`` carries ``market`` / ``investor`` / ``net_buy_krw_100m``
  / ``bizdate`` / ``data_provider`` keys, all stringified.
* ``published_at`` pinned to 15:30 KST on the resolved bizdate → UTC
  (KST is UTC+9, no DST → 06:30 UTC).
* Per-market isolation — KOSPI HTTP 5xx does not drop KOSDAQ items, and
  malformed HTML for one market returns 0 items without raising.
* Tier registration ``"A"``.
* Compliance UA ``Investo/1.0 (...)``.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest

from investo.sources._window import FetchWindow
from investo.sources.krx_foreign_flows import KrxForeignFlowsAdapter
from investo.sources.tiers import adapter_tier

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "api" / "krx-foreign-flows"


def _fixture_bytes(name: str) -> bytes:
    return (_FIXTURE_DIR / name).read_bytes()


def _naver_handler(
    *,
    bodies: dict[tuple[str, str], bytes],
    statuses: dict[tuple[str, str], int] | None = None,
) -> httpx.MockTransport:
    """Build a MockTransport that routes by ``(bizdate, sosok)`` query."""

    statuses = statuses or {}

    def handler(request: httpx.Request) -> httpx.Response:
        bizdate = request.url.params.get("bizdate") or ""
        sosok = request.url.params.get("sosok") or ""
        key = (bizdate, sosok)
        body = bodies.get(key)
        if body is None:
            return httpx.Response(404, content=b"not found")
        return httpx.Response(
            statuses.get(key, 200),
            content=body,
            headers={"content-type": "text/html;charset=EUC-KR"},
        )

    return httpx.MockTransport(handler)


def _all_bodies() -> dict[tuple[str, str], bytes]:
    return {
        ("20260511", "01"): _fixture_bytes("20260511-01.html"),
        ("20260511", "02"): _fixture_bytes("20260511-02.html"),
        ("20260508", "01"): _fixture_bytes("20260508-01.html"),
        ("20260508", "02"): _fixture_bytes("20260508-02.html"),
    }


# ---------------------------------------------------------------------------
# Class identity
# ---------------------------------------------------------------------------


def test_class_attributes() -> None:
    assert KrxForeignFlowsAdapter.name == "krx-foreign-flows"
    assert KrxForeignFlowsAdapter.category == "price"


def test_tier_registered_as_a() -> None:
    assert adapter_tier("krx-foreign-flows") == "A"


# ---------------------------------------------------------------------------
# Happy path — both markets emit 4 items each
# ---------------------------------------------------------------------------


async def test_fetch_kospi_and_kosdaq_yields_eight_items() -> None:
    adapter = KrxForeignFlowsAdapter()
    transport = _naver_handler(bodies=_all_bodies())
    window = FetchWindow.from_kst_date(date(2026, 5, 11))
    async with httpx.AsyncClient(transport=transport) as client:
        items = await adapter.fetch(client, window)
    assert len(items) == 8
    markets = {item.raw_metadata["market"] for item in items}
    assert markets == {"KOSPI", "KOSDAQ"}


async def test_fetch_produces_one_item_per_investor_per_market() -> None:
    adapter = KrxForeignFlowsAdapter()
    transport = _naver_handler(bodies=_all_bodies())
    window = FetchWindow.from_kst_date(date(2026, 5, 11))
    async with httpx.AsyncClient(transport=transport) as client:
        items = await adapter.fetch(client, window)
    pairs = {(item.raw_metadata["market"], item.raw_metadata["investor"]) for item in items}
    expected = {
        (market, investor)
        for market in ("KOSPI", "KOSDAQ")
        for investor in ("individual", "foreign", "institution", "other")
    }
    assert pairs == expected


async def test_recorded_kospi_foreign_amount_matches_fixture() -> None:
    """KOSPI 외국인 net-buy on 2026-05-11 should be -28,147 억원."""
    adapter = KrxForeignFlowsAdapter()
    transport = _naver_handler(bodies=_all_bodies())
    window = FetchWindow.from_kst_date(date(2026, 5, 11))
    async with httpx.AsyncClient(transport=transport) as client:
        items = await adapter.fetch(client, window)
    foreign = next(
        item
        for item in items
        if item.raw_metadata["market"] == "KOSPI" and item.raw_metadata["investor"] == "foreign"
    )
    assert foreign.raw_metadata["net_buy_krw_100m"] == "-28147"
    assert foreign.raw_metadata["bizdate"] == "2026-05-11"
    assert "외국인" in foreign.title
    assert "순매도" in foreign.title
    assert "-28,147" in foreign.title


async def test_recorded_kosdaq_foreign_amount_matches_fixture() -> None:
    """KOSDAQ 외국인 net-buy on 2026-05-11 should be +1,160 억원."""
    adapter = KrxForeignFlowsAdapter()
    transport = _naver_handler(bodies=_all_bodies())
    window = FetchWindow.from_kst_date(date(2026, 5, 11))
    async with httpx.AsyncClient(transport=transport) as client:
        items = await adapter.fetch(client, window)
    foreign = next(
        item
        for item in items
        if item.raw_metadata["market"] == "KOSDAQ" and item.raw_metadata["investor"] == "foreign"
    )
    assert foreign.raw_metadata["net_buy_krw_100m"] == "1160"
    assert "순매수" in foreign.title


async def test_raw_metadata_shape_pins_known_keys() -> None:
    adapter = KrxForeignFlowsAdapter()
    transport = _naver_handler(bodies=_all_bodies())
    window = FetchWindow.from_kst_date(date(2026, 5, 11))
    async with httpx.AsyncClient(transport=transport) as client:
        items = await adapter.fetch(client, window)
    for item in items:
        assert set(item.raw_metadata) == {
            "market",
            "investor",
            "investor_label_ko",
            "net_buy_krw_100m",
            "bizdate",
            "data_provider",
        }
        assert all(isinstance(v, str) for v in item.raw_metadata.values())
        assert item.raw_metadata["data_provider"] == "finance.naver.com (KRX mirror)"


async def test_published_at_pinned_to_kst_close_in_utc() -> None:
    """15:30 KST on 2026-05-11 == 06:30 UTC (no DST in KST)."""
    adapter = KrxForeignFlowsAdapter()
    transport = _naver_handler(bodies=_all_bodies())
    window = FetchWindow.from_kst_date(date(2026, 5, 11))
    async with httpx.AsyncClient(transport=transport) as client:
        items = await adapter.fetch(client, window)
    expected = datetime(2026, 5, 11, 6, 30, tzinfo=UTC)
    for item in items:
        assert item.published_at == expected


# ---------------------------------------------------------------------------
# Weekend / holiday fallback — target date with no exchange session
# ---------------------------------------------------------------------------


async def test_weekend_target_falls_back_to_preceding_business_day() -> None:
    """2026-05-10 is a Sunday → use Friday 2026-05-08 row from each fixture."""
    adapter = KrxForeignFlowsAdapter()
    # Serve the same 2026-05-08-bound fixtures regardless of which
    # bizdate Naver is asked for — emulates the production behaviour
    # where Naver renders the same recent-history table regardless of
    # the requested ``bizdate=`` parameter.
    bodies = {
        ("20260510", "01"): _fixture_bytes("20260508-01.html"),
        ("20260510", "02"): _fixture_bytes("20260508-02.html"),
    }
    transport = _naver_handler(bodies=bodies)
    window = FetchWindow.from_kst_date(date(2026, 5, 10))
    async with httpx.AsyncClient(transport=transport) as client:
        items = await adapter.fetch(client, window)
    assert len(items) == 8
    bizdates = {item.raw_metadata["bizdate"] for item in items}
    assert bizdates == {"2026-05-08"}


# ---------------------------------------------------------------------------
# Per-market isolation — one market fails, sibling survives
# ---------------------------------------------------------------------------


async def test_kospi_5xx_does_not_drop_kosdaq_items() -> None:
    adapter = KrxForeignFlowsAdapter()
    bodies = _all_bodies()
    transport = _naver_handler(bodies=bodies, statuses={("20260511", "01"): 503})
    window = FetchWindow.from_kst_date(date(2026, 5, 11))
    async with httpx.AsyncClient(transport=transport) as client:
        items = await adapter.fetch(client, window)
    # KOSPI dropped (5xx after retries), KOSDAQ delivers its 4 items.
    assert len(items) == 4
    assert {item.raw_metadata["market"] for item in items} == {"KOSDAQ"}


async def test_malformed_html_for_one_market_isolated() -> None:
    adapter = KrxForeignFlowsAdapter()
    # Replace the KOSPI fixture with garbage; KOSDAQ remains intact.
    bodies = {
        ("20260511", "01"): b"<html><body>no table here</body></html>",
        ("20260511", "02"): _fixture_bytes("20260511-02.html"),
    }
    transport = _naver_handler(bodies=bodies)
    window = FetchWindow.from_kst_date(date(2026, 5, 11))
    async with httpx.AsyncClient(transport=transport) as client:
        items = await adapter.fetch(client, window)
    assert len(items) == 4
    assert {item.raw_metadata["market"] for item in items} == {"KOSDAQ"}


# ---------------------------------------------------------------------------
# Compliance — neutral UA, EUC-KR decode round-trip
# ---------------------------------------------------------------------------


async def test_user_agent_is_investo_branded() -> None:
    adapter = KrxForeignFlowsAdapter()
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("user-agent", ""))
        return httpx.Response(
            200,
            content=_fixture_bytes("20260511-01.html"),
            headers={"content-type": "text/html;charset=EUC-KR"},
        )

    window = FetchWindow.from_kst_date(date(2026, 5, 11))
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await adapter.fetch(client, window)
    assert all(ua == "Investo/1.0 (https://murphygo.github.io/investo)" for ua in seen)
    assert seen, "adapter must issue at least one request"


async def test_korean_label_round_trips_through_euc_kr() -> None:
    """Adapter decodes EUC-KR bytes and the Korean label reaches raw_metadata."""
    adapter = KrxForeignFlowsAdapter()
    transport = _naver_handler(bodies=_all_bodies())
    window = FetchWindow.from_kst_date(date(2026, 5, 11))
    async with httpx.AsyncClient(transport=transport) as client:
        items = await adapter.fetch(client, window)
    labels = {item.raw_metadata["investor_label_ko"] for item in items}
    assert labels == {"개인", "외국인", "기관", "기타"}


# ---------------------------------------------------------------------------
# Free-public claim is honest — no Authorization / Cookie / token headers
# ---------------------------------------------------------------------------


async def test_no_auth_headers_attached() -> None:
    adapter = KrxForeignFlowsAdapter()
    seen_headers: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.append(dict(request.headers))
        return httpx.Response(
            200,
            content=_fixture_bytes("20260511-01.html"),
            headers={"content-type": "text/html;charset=EUC-KR"},
        )

    window = FetchWindow.from_kst_date(date(2026, 5, 11))
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await adapter.fetch(client, window)
    for h in seen_headers:
        lowered = {k.lower() for k in h}
        assert "authorization" not in lowered
        assert "cookie" not in lowered
        assert "x-api-key" not in lowered


# ---------------------------------------------------------------------------
# Empty / 0-row fixture — adapter returns [] without raising
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "garbage",
    [
        b"",
        b"<html></html>",
        b"<html><body><table></table></body></html>",
    ],
)
async def test_empty_response_yields_zero_items(garbage: bytes) -> None:
    adapter = KrxForeignFlowsAdapter()
    bodies = {
        ("20260511", "01"): garbage,
        ("20260511", "02"): garbage,
    }
    transport = _naver_handler(bodies=bodies)
    window = FetchWindow.from_kst_date(date(2026, 5, 11))
    async with httpx.AsyncClient(transport=transport) as client:
        items = await adapter.fetch(client, window)
    assert items == []
