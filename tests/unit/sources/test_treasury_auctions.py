"""Tests for ``investo.sources.treasury_auctions.TreasuryAuctionsAdapter``.

Pins the algorithm + R10 fixture replay against:

* The recorded real Fiscal Data body
  (``fixtures/api/treasury-auctions/upcoming.json`` — 23.9 KB live
  recording from 2026-07-19) — forward window filter, coupon-only
  type filter, dedupe, ``scheduled_at`` stamping, nullable
  ``offering_amt``.
* The recorded real empty body
  (``fixtures/api/treasury-auctions/empty_far_future.json`` — live
  recording of a genuinely empty result set) — zero-row degradation.
* Inline synthetic JSON — malformed bodies, env-var overrides, and
  structural edge cases that the live endpoint does not emit.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

import httpx
import pytest

from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceFetchError
from investo.sources.treasury_auctions import TreasuryAuctionsAdapter

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "api" / "treasury-auctions"
_REAL_FIXTURE = _FIXTURE_DIR / "upcoming.json"
_EMPTY_FIXTURE = _FIXTURE_DIR / "empty_far_future.json"

# The recording was taken on this date; the fixture's forward rows run
# 2026-07-20 .. 2026-07-29.
_RECORDED_ON = date(2026, 7, 19)


def _mock_client(body: bytes, status: int = 200) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status,
            content=body,
            headers={"content-type": "application/json"},
        )

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _synthetic(rows: list[dict[str, object]]) -> bytes:
    return json.dumps({"data": rows, "meta": {"count": len(rows)}}).encode("utf-8")


# ---------------------------------------------------------------------------
# Real fixture — happy path against the captured 2026-07-19 snapshot
# ---------------------------------------------------------------------------


async def test_fetch_returns_forward_coupon_auctions() -> None:
    body = _REAL_FIXTURE.read_bytes()
    adapter = TreasuryAuctionsAdapter()
    window = FetchWindow.from_local_date(_RECORDED_ON, tz=UTC)

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items, "expected at least one forward coupon auction in the 30-day window"
    assert all(item.source_name == "treasury-auctions" for item in items)
    assert all(item.category == "calendar" for item in items)


async def test_fetch_excludes_bills_and_cmbs() -> None:
    # The recorded snapshot is 63/100 Bill + 10 CMB. None may appear:
    # the coupon-only default filter is what keeps the 12-row lookahead
    # sub-cap from being flooded with routine cash-management rows.
    body = _REAL_FIXTURE.read_bytes()
    adapter = TreasuryAuctionsAdapter()
    window = FetchWindow.from_local_date(_RECORDED_ON, tz=UTC)

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    types = {item.raw_metadata["security_type"] for item in items}
    assert "Bill" not in types
    assert "CMB" not in types
    assert types <= {"Note", "Bond", "TIPS Note", "TIPS Bond", "FRN Note"}


async def test_fetch_emits_known_ten_year_note_auction() -> None:
    # The recorded fixture carries a 10-Year Note auction on
    # 2026-07-23 (cusip 91282CRE3, $21bn offering).
    body = _REAL_FIXTURE.read_bytes()
    adapter = TreasuryAuctionsAdapter()
    window = FetchWindow.from_local_date(_RECORDED_ON, tz=UTC)

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    matches = [item for item in items if item.raw_metadata.get("cusip") == "91282CRE3"]
    assert len(matches) == 1
    item = matches[0]
    assert item.scheduled_at == datetime(2026, 7, 23, tzinfo=UTC)
    assert item.raw_metadata["security_type"] == "Note"
    assert item.raw_metadata["security_term"] == "10-Year"
    assert item.raw_metadata["offering_amt"] == "21000000000"
    assert "10-Year Note" in item.title
    assert "$21,000,000,000" in (item.summary or "")


async def test_fetch_stamps_tz_aware_utc_and_target_anchored_published_at() -> None:
    body = _REAL_FIXTURE.read_bytes()
    adapter = TreasuryAuctionsAdapter()
    window = FetchWindow.from_local_date(_RECORDED_ON, tz=UTC)

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    expected_published = datetime.combine(_RECORDED_ON, time.min, tzinfo=UTC)
    for item in items:
        # AC-7.4 — tz-aware UTC.
        assert item.scheduled_at is not None
        assert item.scheduled_at.tzinfo is not None
        assert item.scheduled_at.tzinfo.utcoffset(item.scheduled_at) == timedelta(0)
        # published_at is anchored to the target date, not the auction
        # date, so forward rows stay inside the publish window and the
        # aggregator's future-published_at guard does not drop them.
        assert item.published_at == expected_published


async def test_fetch_emits_rows_in_auction_date_order() -> None:
    body = _REAL_FIXTURE.read_bytes()
    adapter = TreasuryAuctionsAdapter()
    window = FetchWindow.from_local_date(_RECORDED_ON, tz=UTC)

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    dates = [item.raw_metadata["auction_date"] for item in items]
    assert dates == sorted(dates)


async def test_fetch_excludes_past_auctions() -> None:
    # The archive spans back to 2024-03; nothing before the target date
    # may leak through.
    body = _REAL_FIXTURE.read_bytes()
    adapter = TreasuryAuctionsAdapter()
    window = FetchWindow.from_local_date(_RECORDED_ON, tz=UTC)

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    for item in items:
        assert date.fromisoformat(item.raw_metadata["auction_date"]) >= _RECORDED_ON


async def test_fetch_is_idempotent() -> None:
    # R9 — same source state yields equal items.
    body = _REAL_FIXTURE.read_bytes()
    adapter = TreasuryAuctionsAdapter()
    window = FetchWindow.from_local_date(_RECORDED_ON, tz=UTC)

    async with _mock_client(body) as client:
        first = await adapter.fetch(client, window)
    async with _mock_client(body) as client:
        second = await adapter.fetch(client, window)

    assert first == second


async def test_fetch_url_is_https_landing_page() -> None:
    body = _REAL_FIXTURE.read_bytes()
    adapter = TreasuryAuctionsAdapter()
    window = FetchWindow.from_local_date(_RECORDED_ON, tz=UTC)

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    for item in items:
        assert str(item.url).startswith("https://")


async def test_raw_metadata_is_flat_string_mapping() -> None:
    # R8 — raw_metadata must be a flat dict[str, str].
    body = _REAL_FIXTURE.read_bytes()
    adapter = TreasuryAuctionsAdapter()
    window = FetchWindow.from_local_date(_RECORDED_ON, tz=UTC)

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    for item in items:
        for key, value in item.raw_metadata.items():
            assert isinstance(key, str)
            assert isinstance(value, str)


# ---------------------------------------------------------------------------
# Real fixture — empty result set
# ---------------------------------------------------------------------------


async def test_fetch_empty_live_recording_returns_no_items() -> None:
    body = _EMPTY_FIXTURE.read_bytes()
    adapter = TreasuryAuctionsAdapter()
    window = FetchWindow.from_local_date(_RECORDED_ON, tz=UTC)

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items == []


async def test_fetch_far_future_target_returns_no_items() -> None:
    # Forward filter is strict: a target date past every recorded
    # auction yields zero rows rather than stale ones.
    body = _REAL_FIXTURE.read_bytes()
    adapter = TreasuryAuctionsAdapter()
    window = FetchWindow.from_local_date(date(2030, 1, 1), tz=UTC)

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items == []


# ---------------------------------------------------------------------------
# Nullable offering amount
# ---------------------------------------------------------------------------


async def test_null_sentinel_offering_amount_is_omitted() -> None:
    body = _synthetic(
        [
            {
                "record_date": "2026-07-17",
                "security_type": "Note",
                "security_term": "5-Year",
                "reopening": "No",
                "cusip": "91282CRA1",
                "offering_amt": "null",
                "announcemt_date": "2026-07-23",
                "auction_date": "2026-07-27",
                "issue_date": "2026-07-31",
            }
        ]
    )
    adapter = TreasuryAuctionsAdapter()
    window = FetchWindow.from_local_date(_RECORDED_ON, tz=UTC)

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert len(items) == 1
    item = items[0]
    assert "offering_amt" not in item.raw_metadata
    assert "not yet announced" in (item.summary or "")
    assert "null" not in (item.summary or "")


# ---------------------------------------------------------------------------
# Dedupe
# ---------------------------------------------------------------------------


async def test_duplicate_auction_keeps_freshest_record_date() -> None:
    # The archive can carry the same auction under two record_date
    # snapshots; the newer one (with the announced amount) must win.
    rows: list[dict[str, object]] = [
        {
            "record_date": "2026-07-10",
            "security_type": "Note",
            "security_term": "10-Year",
            "reopening": "No",
            "cusip": "91282CRE3",
            "offering_amt": "null",
            "auction_date": "2026-07-23",
        },
        {
            "record_date": "2026-07-17",
            "security_type": "Note",
            "security_term": "10-Year",
            "reopening": "No",
            "cusip": "91282CRE3",
            "offering_amt": "21000000000",
            "auction_date": "2026-07-23",
        },
    ]
    adapter = TreasuryAuctionsAdapter()
    window = FetchWindow.from_local_date(_RECORDED_ON, tz=UTC)

    async with _mock_client(_synthetic(rows)) as client:
        items = await adapter.fetch(client, window)

    assert len(items) == 1
    assert items[0].raw_metadata["offering_amt"] == "21000000000"


# ---------------------------------------------------------------------------
# Env-var overrides (R12)
# ---------------------------------------------------------------------------


async def test_auction_types_override_admits_bills(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INVESTO_TREASURY_AUCTION_TYPES", "Bill")
    body = _REAL_FIXTURE.read_bytes()
    adapter = TreasuryAuctionsAdapter()
    window = FetchWindow.from_local_date(_RECORDED_ON, tz=UTC)

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items
    assert {item.raw_metadata["security_type"] for item in items} == {"Bill"}


async def test_lookahead_days_override_narrows_window() -> None:
    body = _REAL_FIXTURE.read_bytes()
    adapter = TreasuryAuctionsAdapter()
    window = FetchWindow.from_local_date(_RECORDED_ON, tz=UTC)

    async with _mock_client(body) as client:
        wide = await adapter.fetch(client, window)

    os.environ["INVESTO_TREASURY_AUCTION_LOOKAHEAD_DAYS"] = "3"
    try:
        async with _mock_client(body) as client:
            narrow = await adapter.fetch(client, window)
    finally:
        del os.environ["INVESTO_TREASURY_AUCTION_LOOKAHEAD_DAYS"]

    assert len(narrow) < len(wide)
    for item in narrow:
        assert date.fromisoformat(item.raw_metadata["auction_date"]) < _RECORDED_ON + timedelta(
            days=3
        )


@pytest.mark.parametrize("value", ["", "abc", "0", "-5"])
async def test_invalid_lookahead_days_falls_back_to_default(
    value: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = _REAL_FIXTURE.read_bytes()
    adapter = TreasuryAuctionsAdapter()
    window = FetchWindow.from_local_date(_RECORDED_ON, tz=UTC)

    async with _mock_client(body) as client:
        baseline = await adapter.fetch(client, window)

    monkeypatch.setenv("INVESTO_TREASURY_AUCTION_LOOKAHEAD_DAYS", value)
    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items == baseline


async def test_lookahead_days_above_max_is_clamped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INVESTO_TREASURY_AUCTION_LOOKAHEAD_DAYS", "9999")
    body = _REAL_FIXTURE.read_bytes()
    adapter = TreasuryAuctionsAdapter()
    window = FetchWindow.from_local_date(_RECORDED_ON, tz=UTC)

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    # Clamped to 180 days — every row stays inside that bound.
    for item in items:
        assert date.fromisoformat(item.raw_metadata["auction_date"]) < _RECORDED_ON + timedelta(
            days=180
        )


# ---------------------------------------------------------------------------
# Malformed / hostile payloads (R6)
# ---------------------------------------------------------------------------


async def test_malformed_json_raises_source_fetch_error() -> None:
    adapter = TreasuryAuctionsAdapter()
    window = FetchWindow.from_local_date(_RECORDED_ON, tz=UTC)

    async with _mock_client(b"not json at all") as client:
        with pytest.raises(SourceFetchError) as excinfo:
            await adapter.fetch(client, window)

    assert excinfo.value.transient is False
    assert excinfo.value.source_name == "treasury-auctions"


async def test_non_object_payload_raises_source_fetch_error() -> None:
    adapter = TreasuryAuctionsAdapter()
    window = FetchWindow.from_local_date(_RECORDED_ON, tz=UTC)

    async with _mock_client(b"[1, 2, 3]") as client:
        with pytest.raises(SourceFetchError) as excinfo:
            await adapter.fetch(client, window)

    assert excinfo.value.transient is False


async def test_non_list_data_raises_source_fetch_error() -> None:
    adapter = TreasuryAuctionsAdapter()
    window = FetchWindow.from_local_date(_RECORDED_ON, tz=UTC)

    async with _mock_client(b'{"data": {"oops": 1}}') as client:
        with pytest.raises(SourceFetchError) as excinfo:
            await adapter.fetch(client, window)

    assert excinfo.value.transient is False


async def test_missing_data_key_returns_empty() -> None:
    adapter = TreasuryAuctionsAdapter()
    window = FetchWindow.from_local_date(_RECORDED_ON, tz=UTC)

    async with _mock_client(b'{"meta": {}}') as client:
        items = await adapter.fetch(client, window)

    assert items == []


async def test_rows_with_unusable_fields_are_skipped() -> None:
    rows: list[dict[str, object]] = [
        "not a dict",  # type: ignore[list-item]
        {"security_type": "Note", "auction_date": "not-a-date"},
        {"security_type": None, "auction_date": "2026-07-23"},
        {"auction_date": "2026-07-23"},
    ]
    adapter = TreasuryAuctionsAdapter()
    window = FetchWindow.from_local_date(_RECORDED_ON, tz=UTC)

    async with _mock_client(_synthetic(rows)) as client:
        items = await adapter.fetch(client, window)

    assert items == []


async def test_http_error_raises_source_fetch_error() -> None:
    adapter = TreasuryAuctionsAdapter()
    window = FetchWindow.from_local_date(_RECORDED_ON, tz=UTC)

    async with _mock_client(b"server exploded", status=500) as client:
        with pytest.raises(SourceFetchError):
            await adapter.fetch(client, window)
