"""Flat groups through the real collection/calculation/pair-store boundaries."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError
from tests.unit.sector_dashboard.test_public_probe import _TARGET, _json

from investo.models.market_groups import (
    ADDITIONAL_REQUEST_TICKERS,
    GROUP_DEFINITIONS,
    HARDWARE_MEMBERS,
    MARKET_GROUP_IDS,
    AdditionalAssetTicker,
    GroupKind,
    MarketGroupId,
    expected_asset_type,
)
from investo.models.sector import SectorTicker
from investo.models.sector_public import (
    PUBLIC_REQUEST_TICKERS,
    PublicSectorBuildStatus,
    PublicSectorDashboardSnapshot,
    SectorAvailability,
    ValuePoint,
)
from investo.sector_dashboard.public_build import build_public_sector
from investo.sector_dashboard.public_groups import (
    attach_public_market_groups,
    representative_price_index,
)
from investo.sector_dashboard.public_metrics import (
    build_public_series_bundle,
    compute_public_sector_snapshot,
)
from investo.sector_dashboard.public_probe import probe_public_sector
from investo.sector_dashboard.public_render import (
    render_public_sector_projection,
    verify_public_sector_projection,
)
from investo.sector_dashboard.public_store import read_public_sector_projection
from investo.sector_dashboard.yahoo_data import YahooRequestBudget, collect_public_bars

_ROOT = Path(__file__).resolve().parents[3]


def _transport(
    calls: list[str],
    *,
    failure: str | None = None,
    status: int = 404,
    short: str | None = None,
    wrong_type: str | None = None,
    varied: bool = False,
) -> httpx.MockTransport:
    """Independent mixed ETF/equity provider fixture; never production data."""
    identities = (*PUBLIC_REQUEST_TICKERS, *ADDITIONAL_REQUEST_TICKERS)

    def handler(request: httpx.Request) -> httpx.Response:
        ticker = request.url.path.rsplit("/", 1)[1]
        calls.append(ticker)
        assert request.url.host == "query2.finance.yahoo.com"
        assert request.headers["user-agent"] == "investo-sector-dashboard/2.0"
        assert "authorization" not in request.headers and "x-api-key" not in request.headers
        if ticker == failure:
            return httpx.Response(status, text="credential-sentinel-never-export")
        identity = next(item for item in identities if item.value == ticker)
        payload = json.loads(_json(count=63 if ticker == short else 64))
        result = payload["chart"]["result"][0]
        result["meta"]["symbol"] = ticker
        result["meta"]["instrumentType"] = expected_asset_type(identity)
        if ticker == wrong_type:
            result["meta"]["instrumentType"] = (
                "ETF" if expected_asset_type(identity) == "EQUITY" else "EQUITY"
            )
        if varied:
            slope = (identities.index(identity) + 1) / 50
            prices = [100 + index * slope for index in range(64)]
            result["indicators"]["quote"][0].update(
                open=prices, close=prices, high=[p + 1 for p in prices], low=[p - 1 for p in prices]
            )
        return httpx.Response(200, json=payload)

    return httpx.MockTransport(handler)


async def _snapshots(**kwargs: object):
    calls: list[str] = []
    async with httpx.AsyncClient(transport=_transport(calls, **kwargs)) as client:
        parsed = await collect_public_bars(client, target_date=_TARGET, include_market_groups=True)
    bundle = build_public_series_bundle(parsed, target_date=_TARGET)
    original = compute_public_sector_snapshot(bundle)
    assert parsed.additional is not None
    expanded = attach_public_market_groups(original, bundle, parsed.additional)
    return original, expanded, parsed, calls


@pytest.mark.asyncio
async def test_full_universe_has_distinct_rank_denominators_and_preserves_overview() -> None:
    original, expanded, parsed, calls = await _snapshots(varied=True)
    assert len(calls) == len(set(calls)) == 23
    assert set(calls) == {t.value for t in (*PUBLIC_REQUEST_TICKERS, *ADDITIONAL_REQUEST_TICKERS)}
    assert parsed.additional is not None and len(parsed.additional.assets) == 11
    assert len(parsed.sectors) == 11 and len(expanded.records) == 11
    assert expanded.records == original.records
    groups = expanded.market_groups
    assert expanded.schema_version == 3 and groups is not None
    assert groups.as_of_date == original.as_of_date == _TARGET
    assert groups.available_group_count == groups.comparable_group_count == 14
    assert tuple(r.group_id for r in groups.records) == MARKET_GROUP_IDS
    assert all(r.relative_rank.comparable_group_count == 14 for r in groups.records)
    assert all(r.relative_rank.comparable_sector_count == 11 for r in expanded.records)
    assert not any(r.members == (SectorTicker.XLK,) for r in groups.records)
    for group in groups.records:
        if isinstance(group.members[0], SectorTicker):
            sector = next(r for r in original.records if r.ticker is group.members[0])
            assert group.metrics.model_dump() == sector.metrics.model_dump(exclude={"ticker"})
    big_tech = next(r for r in groups.records if r.group_id is MarketGroupId.BIG_TECH)
    hardware = next(r for r in groups.records if r.group_id is MarketGroupId.HARDWARE)
    assert big_tech.kind is GroupKind.THEME and big_tech.members == (AdditionalAssetTicker.MAGS,)
    assert hardware.kind is GroupKind.REPRESENTATIVE and hardware.members == HARDWARE_MEMBERS


@pytest.mark.asyncio
async def test_zero_relative_returns_receive_stable_full_universe_ties() -> None:
    _, expanded, _, _ = await _snapshots()
    assert expanded.market_groups is not None
    ranks = [r.relative_rank for r in expanded.market_groups.records]
    assert {r.score for r in ranks} == {Decimal("0.5")}
    assert [r.ordinal for r in ranks] == list(range(1, 15))
    assert all(r.metrics.price_excess_21d.value == 0 for r in expanded.market_groups.records)


def test_daily_equal_weight_index_uses_returns_and_is_price_scale_invariant() -> None:
    from tests.unit.sector_dashboard.test_public_render_store import _trading_dates

    days = _trading_dates(64)
    first = [Decimal(100), Decimal(110), Decimal(99)] + [Decimal(99)] * 61
    second = [Decimal(200), Decimal(180), Decimal(198)] + [Decimal(198)] * 61

    def points(values: list[Decimal], scale: int = 1) -> tuple[ValuePoint, ...]:
        return tuple(
            ValuePoint(trading_date=d, value=v * scale) for d, v in zip(days, values, strict=True)
        )

    result = representative_price_index((points(first), points(second)), days)
    scaled = representative_price_index((points(first, 10), points(second, 3)), days)
    # +10% and -10%, then -10% and +10%: daily equal weights stay flat.
    assert all(point.value == Decimal(100) for point in result)
    assert result == scaled
    with pytest.raises(ValueError, match="cannot fill"):
        representative_price_index((points(first)[:-1], points(second)), days)
    with pytest.raises(ValueError, match="requires"):
        representative_price_index((), days)


@given(
    first=st.lists(st.integers(10, 1000), min_size=64, max_size=64),
    second=st.lists(st.integers(10, 1000), min_size=64, max_size=64),
    first_scale=st.integers(1, 20),
    second_scale=st.integers(1, 20),
)
@settings(max_examples=25)
def test_basket_price_scale_property(first, second, first_scale, second_scale) -> None:
    from tests.unit.sector_dashboard.test_public_render_store import _trading_dates

    days = _trading_dates(64)

    def points(values, scale):
        return tuple(
            ValuePoint(trading_date=d, value=Decimal(v * scale))
            for d, v in zip(days, values, strict=True)
        )

    baseline = representative_price_index((points(first, 1), points(second, 1)), days)
    scaled = representative_price_index(
        (points(first, first_scale), points(second, second_scale)), days
    )
    assert baseline == scaled


@pytest.mark.asyncio
async def test_weighted_score_ties_follow_fixed_identity_not_first_horizon_order() -> None:
    from investo.models.sector import MetricValue
    from investo.sector_dashboard.public_groups import _rank_groups

    _, expanded, _, _ = await _snapshots()
    assert expanded.market_groups is not None
    records = list(expanded.market_groups.records)
    for position, sign in ((0, -1), (1, 1)):
        metrics = records[position].metrics.model_copy(
            update={
                "price_excess_5d": MetricValue(value=Decimal(sign)),
                "price_excess_21d": MetricValue(value=Decimal(-sign)),
                "price_excess_63d": MetricValue(value=Decimal(sign)),
            }
        )
        records[position] = records[position].model_copy(update={"metrics": metrics})
    ranked = _rank_groups(records)
    assert {r.relative_rank.score for r in ranked} == {Decimal("0.5")}
    assert [r.relative_rank.ordinal for r in ranked] == list(range(1, 15))


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["snapshot_promoted", "markdown_promoted"])
async def test_schema3_store_failure_restores_prior_pair(tmp_path: Path, phase: str) -> None:
    from investo.sector_dashboard.public_store import (
        PublicSectorStoreError,
        promote_public_sector_projection,
    )

    (tmp_path / "site_docs").mkdir()
    _, first, _, _ = await _snapshots()
    _, second, _, _ = await _snapshots(varied=True)
    prior = render_public_sector_projection(first)
    promote_public_sector_projection(tmp_path, prior)

    def fail(point: str) -> None:
        if point == phase:
            raise RuntimeError("synthetic promotion failure")

    with pytest.raises(PublicSectorStoreError):
        promote_public_sector_projection(
            tmp_path, render_public_sector_projection(second), _fault_hook=fail
        )
    assert read_public_sector_projection(tmp_path) == prior


@pytest.mark.asyncio
@pytest.mark.parametrize("member", HARDWARE_MEMBERS)
@pytest.mark.parametrize("problem", ["missing", "short", "identity"])
async def test_any_bad_hardware_member_suppresses_entire_basket(member, problem: str) -> None:
    kwargs = {"missing": "failure", "short": "short", "identity": "wrong_type"}
    original, expanded, parsed, _ = await _snapshots(**{kwargs[problem]: member.value})
    groups = expanded.market_groups
    assert groups is not None and groups.available_group_count == 13
    record = next(r for r in groups.records if r.group_id is MarketGroupId.HARDWARE)
    assert record.availability is SectorAvailability.TEMPORARILY_UNAVAILABLE
    assert all(metric.value is None for _, metric in record.metrics)
    assert record.relative_rank.score is None
    assert all(r.relative_rank.comparable_group_count == 13 for r in groups.records)
    assert original.records == expanded.records
    assert parsed.additional is not None
    if problem != "short":
        assert member not in parsed.additional.assets


@pytest.mark.asyncio
@pytest.mark.parametrize("ticker", ["SMH", "XSW", "MAGS"])
async def test_fund_identity_mismatch_does_not_publish_an_equity_as_an_etf(ticker: str) -> None:
    _, expanded, _, _ = await _snapshots(wrong_type=ticker)
    assert expanded.market_groups is not None
    assert expanded.market_groups.available_group_count == 13


@pytest.mark.asyncio
async def test_benchmark_auth_rejection_stops_expanded_fanout_and_secrets_stay_closed() -> None:
    calls: list[str] = []
    budget = YahooRequestBudget()
    async with httpx.AsyncClient(transport=_transport(calls, failure="SPY", status=401)) as client:
        parsed = await collect_public_bars(
            client, target_date=_TARGET, include_market_groups=True, budget=budget
        )
    assert calls == ["SPY"] and budget.request_count == 1
    assert len(parsed.failures) == 12
    assert parsed.additional is not None and len(parsed.additional.failures) == 11
    assert not parsed.additional.assets
    assert "credential-sentinel" not in repr(parsed)


@pytest.mark.asyncio
async def test_expansion_shares_36_attempt_budget_under_many_retryable_failures() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        ticker = request.url.path.rsplit("/", 1)[1]
        if ticker == "SPY":
            return _transport(calls).handle_request(request)
        calls.append(ticker)
        return httpx.Response(503)

    budget = YahooRequestBudget()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        parsed = await collect_public_bars(
            client, target_date=_TARGET, include_market_groups=True, budget=budget
        )
    assert len(calls) == budget.request_count == 36
    assert parsed.benchmark is not None and len(parsed.failures) == 11
    assert parsed.additional is not None and len(parsed.additional.failures) == 11


@pytest.mark.asyncio
async def test_closed_snapshot_roundtrip_and_data_first_render() -> None:
    _, expanded, _, _ = await _snapshots(varied=True)
    projection = render_public_sector_projection(expanded)
    verified = verify_public_sector_projection(projection.snapshot_bytes, projection.markdown_bytes)
    assert verified == expanded
    text = projection.markdown_bytes.decode()
    assert text.index("## 분야별 비교") < text.index("## 시장 요약") < text.index("## 방법과 출처")
    assert text.count('data-testid="sector-row-') == 14
    assert text.count('data-testid="sector-bar-') == 14
    assert 'data-testid="sector-filter-technology"' in text
    assert 'role="tabpanel"' in text and "소프트웨어·IT서비스" in text
    assert "대표주 바스켓" in text and "종목이 겹칠" in text
    payload = json.loads(projection.snapshot_bytes)
    assert "bars" not in payload and "points" not in payload and "volume" not in payload
    assert PublicSectorDashboardSnapshot.model_validate(payload) == expanded


def test_committed_schema2_pair_remains_byte_exact() -> None:
    projection = read_public_sector_projection(_ROOT)
    assert projection is not None
    original = verify_public_sector_projection(projection.snapshot_bytes, projection.markdown_bytes)
    if original.schema_version != 2:
        pytest.skip("committed dataset migrated; schema2 fixture tested separately")
    assert "market_groups" not in original.model_dump(mode="json")
    assert render_public_sector_projection(original) == projection


def test_schema2_projection_preserves_legacy_golden_bytes_after_live_migration() -> None:
    from tests.unit.sector_dashboard.test_public_render_store import _snapshot

    projection = render_public_sector_projection(_snapshot())
    assert hashlib.sha256(projection.snapshot_bytes).hexdigest() == (
        "d04f379baa4c8f1650aefa0c24a57f50350b116d6e18bf31315d9209a5e507e6"
    )
    assert hashlib.sha256(projection.markdown_bytes).hexdigest() == (
        "da4b0d18393ba393951e6652e46dcdd10edc1a7ae77accf37d21af0942c8c9a8"
    )


@pytest.mark.asyncio
async def test_fewer_than_eight_flat_comparables_suppress_every_group_rank() -> None:
    excluded = {t.value for t in ADDITIONAL_REQUEST_TICKERS} | {"XLC", "XLY", "XLP"}
    transport = _transport([])

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.rsplit("/", 1)[1] in excluded:
            return httpx.Response(404)
        return transport.handle_request(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        parsed = await collect_public_bars(client, target_date=_TARGET, include_market_groups=True)
    bundle = build_public_series_bundle(parsed, target_date=_TARGET)
    original = compute_public_sector_snapshot(bundle)
    assert original.coverage.available_sector_count == 8 and parsed.additional is not None
    expanded = attach_public_market_groups(original, bundle, parsed.additional)
    assert expanded.market_groups is not None
    assert expanded.market_groups.comparable_group_count == 7
    assert all(r.relative_rank.score is None for r in expanded.market_groups.records)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tamper",
    ["metadata", "member", "date", "count", "duplicate", "rank", "schema", "raw", "reused"],
)
async def test_group_contract_rejects_inconsistent_or_unclosed_payload(tamper: str) -> None:
    _, expanded, _, _ = await _snapshots()
    data = deepcopy(expanded.model_dump(mode="json"))
    groups = data["market_groups"]
    record = groups["records"][-1]
    if tamper == "metadata":
        record["scope"] = "arbitrary provider text"
    elif tamper == "member":
        record["members"] = ["SPY"]
    elif tamper == "date":
        groups["as_of_date"] = "2026-09-24"
    elif tamper == "count":
        groups["available_group_count"] = 13
    elif tamper == "duplicate":
        groups["records"][-1] = groups["records"][0]
    elif tamper == "rank":
        record["relative_rank"]["ordinal"] = 1
    elif tamper == "schema":
        data["schema_version"] = 2
    elif tamper == "raw":
        record["raw_rows"] = []
    else:
        groups["records"][0]["metrics"]["price_excess_21d"]["value"] = "123"
    with pytest.raises(ValidationError):
        PublicSectorDashboardSnapshot.model_validate(data)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [None, "MAGS", "HPE", "SPY"])
async def test_read_only_probe_requires_every_new_group(
    tmp_path: Path, monkeypatch, failure
) -> None:
    monkeypatch.chdir(tmp_path)
    initial_paths = set(tmp_path.rglob("*"))
    calls: list[str] = []
    async with httpx.AsyncClient(transport=_transport(calls, failure=failure)) as client:
        evidence = await probe_public_sector(
            client, target_date=_TARGET, include_market_groups=True
        )
    assert evidence.requested_symbol_count == 23
    assert (evidence.status == "qualified") is (failure is None)
    assert evidence.available_group_count == (
        14 if failure is None else 0 if failure == "SPY" else 13
    )
    assert set(tmp_path.rglob("*")) == initial_paths
    assert "credential-sentinel" not in evidence.model_dump_json()


@pytest.mark.asyncio
async def test_schema2_to3_atomic_migration_unchanged_and_last_good_hold(tmp_path: Path) -> None:
    (tmp_path / "site_docs").mkdir()
    async with httpx.AsyncClient(transport=_transport([])) as client:
        legacy = await build_public_sector(client, repository_root=tmp_path, target_date=_TARGET)
    assert legacy.status is PublicSectorBuildStatus.PROMOTED
    async with httpx.AsyncClient(transport=_transport([])) as client:
        result = await build_public_sector(
            client, repository_root=tmp_path, target_date=_TARGET, include_market_groups=True
        )
    assert result.status is PublicSectorBuildStatus.PROMOTED and result.exit_code == 0
    files = [tmp_path / "site_docs/sectors" / name for name in ("index.md", "latest.json")]
    before = [(p.read_bytes(), p.stat().st_mtime_ns) for p in files]
    async with httpx.AsyncClient(transport=_transport([])) as client:
        repeat = await build_public_sector(
            client, repository_root=tmp_path, target_date=_TARGET, include_market_groups=True
        )
    assert repeat.status is PublicSectorBuildStatus.UNCHANGED
    assert before == [(p.read_bytes(), p.stat().st_mtime_ns) for p in files]
    async with httpx.AsyncClient(transport=_transport([], failure="SPY", status=401)) as client:
        held = await build_public_sector(
            client, repository_root=tmp_path, target_date=_TARGET, include_market_groups=True
        )
    assert held.status is PublicSectorBuildStatus.HELD_LAST_GOOD and held.exit_code == 2
    assert before == [(p.read_bytes(), p.stat().st_mtime_ns) for p in files]
    projection = read_public_sector_projection(tmp_path)
    assert projection is not None
    assert (
        verify_public_sector_projection(
            projection.snapshot_bytes, projection.markdown_bytes
        ).schema_version
        == 3
    )


@pytest.mark.asyncio
async def test_missing_extra_group_promotes_usable_overview_but_signals_partial(
    tmp_path: Path,
) -> None:
    (tmp_path / "site_docs").mkdir()
    async with httpx.AsyncClient(transport=_transport([], failure="MAGS")) as client:
        result = await build_public_sector(
            client, repository_root=tmp_path, target_date=_TARGET, include_market_groups=True
        )
    assert result.status is PublicSectorBuildStatus.PROMOTED and result.exit_code == 2
    assert result.available_sector_count == 11 and result.available_group_count == 13
    projection = read_public_sector_projection(tmp_path)
    assert projection is not None
    snapshot = verify_public_sector_projection(projection.snapshot_bytes, projection.markdown_bytes)
    assert snapshot.market_groups is not None and snapshot.market_groups.available_group_count == 13


def test_flat_groups_have_fixed_unique_identities_and_explicit_measurement_scope() -> None:
    assert len(GROUP_DEFINITIONS) == len(set(MARKET_GROUP_IDS)) == 14
    assert len(ADDITIONAL_REQUEST_TICKERS) == 11
    assert not set(ADDITIONAL_REQUEST_TICKERS) & set(PUBLIC_REQUEST_TICKERS)
