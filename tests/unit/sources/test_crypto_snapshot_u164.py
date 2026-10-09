"""Live crypto observations preserve receipt time and unknown metrics."""

import json
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import pytest
import yaml
from hypothesis import given
from hypothesis import strategies as st

import investo.sources.aggregator as aggregator_module
import investo.sources.coingecko as coingecko_module
from investo._internal.price_time_basis import price_snapshot_label
from investo.briefing._core.orchestration import serialize_items_for_prompt
from investo.notifier._summary_extract import market_snapshot_entries
from investo.notifier.summary import _format_snapshot_entry
from investo.publisher.watchpoint_matrix import WatchpointItemSnapshot, _coingecko_candidate
from investo.sources._window import FetchWindow
from investo.sources.coingecko import CoinGeckoPriceAdapter, _finite_number
from investo.visuals import build_price_snapshot_card, render_card_svg

_DATE = date(2026, 10, 8)
_RUN = datetime(2026, 10, 9, 0, 3, tzinfo=UTC)
_RECEIVED = _RUN + timedelta(minutes=3)


def _entry(*, as_of: datetime, symbol: str = "btc", **metrics: object) -> dict[str, object]:
    return {
        "id": {"btc": "bitcoin", "eth": "ethereum", "sol": "solana"}[symbol],
        "symbol": symbol,
        "current_price": 123.45,
        "last_updated": as_of.isoformat(),
        **metrics,
    }


async def _fetch(
    monkeypatch: pytest.MonkeyPatch, entries: list[dict[str, object]], *, live: bool = True
):
    monkeypatch.setattr(coingecko_module, "_utc_now", lambda: _RECEIVED)
    window = FetchWindow.from_local_date(_DATE, ZoneInfo("UTC"))
    if live:
        window = replace(window, price_snapshot_at=_RUN)
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                content=json.dumps(entries).encode(),
                headers={"content-type": "application/json"},
            )
        )
    )
    async with client:
        return await CoinGeckoPriceAdapter().fetch(client, window)


async def test_three_live_coins_retain_provider_time_and_replay_excludes_them(monkeypatch):
    as_of = _RECEIVED - timedelta(seconds=2)
    entries = [_entry(as_of=as_of, symbol=s) for s in ("btc", "eth", "sol")]
    live = await _fetch(monkeypatch, entries)
    assert len(live) == 3
    assert await _fetch(monkeypatch, entries, live=False) == []
    for item in live:
        assert item.published_at == as_of
        assert item.raw_metadata["observed_at"] == _RECEIVED.isoformat()
        assert item.raw_metadata["price_snapshot_reference_at"] == _RUN.isoformat()
        assert item.raw_metadata["report_target_date"] == _DATE.isoformat()
        assert "조회 시점 가격" in item.title
        assert "CoinGecko" in (item.summary or "")


async def test_real_collector_threads_permission_without_changing_outcome_health(monkeypatch):
    as_of = _RECEIVED - timedelta(seconds=1)
    entries = [_entry(as_of=as_of, symbol=s) for s in ("btc", "eth", "sol")]
    client_class = httpx.AsyncClient
    monkeypatch.setattr(aggregator_module, "list_sources", lambda: [CoinGeckoPriceAdapter()])
    monkeypatch.setattr(coingecko_module, "_utc_now", lambda: _RECEIVED)
    monkeypatch.setattr(
        aggregator_module.httpx,
        "AsyncClient",
        lambda: client_class(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json=entries))
        ),
    )
    live = await aggregator_module.collect_sources(_DATE, price_snapshot_at=_RUN)
    assert len(live.items) == 3
    assert live.outcomes[0].status == "ok"
    assert live.outcomes[0].latest_item_at == as_of
    assert live.outcomes[0].item_count == 3
    replay = await aggregator_module.collect_sources(_DATE)
    assert replay.items == ()
    assert replay.outcomes[0].status == "zero"


@pytest.mark.parametrize(
    "delta,kept",
    (
        (timedelta(hours=6), True),
        (timedelta(hours=6, microseconds=1), False),
        (timedelta(0), True),
        (timedelta(microseconds=-1), False),
    ),
)
async def test_exact_receipt_freshness_and_future_boundaries(monkeypatch, delta, kept):
    items = await _fetch(monkeypatch, [_entry(as_of=_RECEIVED - delta)])
    assert bool(items) is kept


@pytest.mark.parametrize("value", (None, "bad", True, float("nan"), float("inf"), -1))
async def test_bad_optional_metrics_are_omitted_but_price_survives(monkeypatch, value):
    item = (
        await _fetch(
            monkeypatch,
            [
                _entry(
                    as_of=_RECEIVED,
                    price_change_percentage_24h=None if value == -1 else value,
                    total_volume=value,
                    market_cap=value,
                    high_24h=value,
                    low_24h=value,
                )
            ],
        )
    )[0]
    for key in ("pct_24h", "volume_24h", "market_cap", "high_24h", "low_24h"):
        assert key not in item.raw_metadata
    assert "(+0.00%)" not in item.title


@pytest.mark.parametrize("value", (None, True, 0, -1, float("nan"), float("inf"), "123"))
async def test_invalid_current_price_does_not_erase_valid_siblings(monkeypatch, value):
    entries = [_entry(as_of=_RECEIVED, current_price=value), _entry(as_of=_RECEIVED, symbol="eth")]
    items = await _fetch(monkeypatch, entries)
    assert [item.raw_metadata["symbol"] for item in items] == ["eth"]


async def test_unknown_metrics_and_live_basis_reach_real_consumers(monkeypatch):
    item = (await _fetch(monkeypatch, [_entry(as_of=_RECEIVED)]))[0]
    prompt = json.loads(serialize_items_for_prompt([item]))[0]
    assert prompt["price_observation"]["price_as_of"] == _RECEIVED.isoformat()
    assert prompt["ts"] == _RECEIVED.isoformat()
    card = build_price_snapshot_card(_DATE, "crypto", [item])
    assert card is not None
    assert card.rows[0].percent_change == "미확인"
    assert card.rows[0].volume is card.rows[0].high is card.rows[0].low is None
    svg = render_card_svg(card)
    assert "조회 시점 가격" in svg and "2026-10-09 00:06" in svg
    assert "+0.00%" not in svg
    candidate = _coingecko_candidate(WatchpointItemSnapshot.from_item(item))
    assert candidate is not None
    assert "조회 시점 가격" in candidate.current and "2026-10-09 00:06" in candidate.current
    assert "+0.00%" not in candidate.current
    entry = next(entry for entry in market_snapshot_entries([item]) if entry.label == "BTC")
    assert entry.pct is None and entry.price == 123.45
    assert "조회 시점 가격" in _format_snapshot_entry(entry)


async def test_free_demo_key_uses_only_header_on_public_host(monkeypatch):
    monkeypatch.setenv("COINGECKO_DEMO_API_KEY", "synthetic-demo-key")
    monkeypatch.setattr(coingecko_module, "_utc_now", lambda: _RECEIVED)
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=[_entry(as_of=_RECEIVED)])

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await CoinGeckoPriceAdapter().fetch(
            client, replace(FetchWindow.from_kst_date(_DATE), price_snapshot_at=_RUN)
        )
    assert len(requests) == 1
    assert requests[0].url.host == "api.coingecko.com"
    assert requests[0].headers["x-cg-demo-api-key"] == "synthetic-demo-key"
    assert "synthetic-demo-key" not in str(requests[0].url)
    assert "x-cg-pro-api-key" not in requests[0].headers


@pytest.mark.parametrize(
    "path", (".github/workflows/daily-briefing.yml", "ops/private-runtime/production-briefing.yml")
)
def test_optional_free_demo_key_is_wired_to_the_run_step(path):
    workflow = yaml.safe_load(Path(path).read_text())
    env_values = [
        step.get("env", {})
        for job in workflow["jobs"].values()
        for step in job.get("steps", ())
        if "COINGECKO_DEMO_API_KEY" in step.get("env", {})
    ]
    assert len(env_values) == 1
    assert env_values[0]["COINGECKO_DEMO_API_KEY"] == "${{ secrets.COINGECKO_DEMO_API_KEY }}"


def test_snapshot_permission_requires_aware_clock():
    with pytest.raises(ValueError, match="price_snapshot_at"):
        replace(FetchWindow.from_kst_date(_DATE), price_snapshot_at=datetime(2026, 10, 9))
    window = replace(FetchWindow.from_kst_date(_DATE), price_snapshot_at=_RUN)
    assert window.lookahead(2).price_snapshot_at == _RUN


@given(st.floats(allow_nan=False, allow_infinity=False, min_value=0, max_value=1e15))
def test_real_finite_zero_and_metrics_are_preserved(value):
    assert _finite_number(value, nonnegative=True) == value


@given(
    st.datetimes(
        timezones=st.just(UTC), min_value=datetime(2000, 1, 1), max_value=datetime(2099, 1, 1)
    )
)
def test_display_basis_is_explicit_and_utc(as_of):
    label = price_snapshot_label(
        {"price_time_basis": "live_snapshot", "price_as_of": as_of.isoformat()}
    )
    assert label == f"조회 시점 가격 · {as_of:%Y-%m-%d %H:%M} UTC"
