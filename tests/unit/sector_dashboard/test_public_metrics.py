"""Step 3 tests for the derived-only public sector snapshot computation."""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
from datetime import date, timedelta
from decimal import Decimal

import pytest

from investo.models.market_calendar import is_trading_day
from investo.models.sector import (
    BENCHMARK_TICKER,
    SECTOR_TICKERS,
    MetricMissingReason,
    SectorCoverageStatus,
    SectorRegime,
    SectorTicker,
)
from investo.models.sector_public import (
    PUBLIC_REQUEST_TICKERS,
    PUBLIC_SUPPORTED_SECTOR_TICKERS,
    REQUIRED_PUBLIC_ATTRIBUTIONS,
    FreshnessState,
    MarketScope,
    PublicBarPoint,
    PublicBarSeries,
    PublicDiagnosticCode,
    PublicParsedSet,
    PublicSourceFailure,
    PublicSourceIssueCode,
    SectorAvailability,
)
from investo.sector_dashboard import public_metrics
from investo.sector_dashboard.public_metrics import (
    build_public_series_bundle,
    compute_public_sector_metrics,
    compute_public_sector_snapshot,
    resolve_public_freshness,
)

_AS_OF = date(2026, 8, 31)


def _trading_dates(count: int, *, end: date = _AS_OF) -> tuple[date, ...]:
    days: list[date] = []
    cursor = end
    while len(days) < count:
        if is_trading_day("us-equity", cursor):
            days.append(cursor)
        cursor -= timedelta(days=1)
    return tuple(reversed(days))


def _bars(
    ticker: SectorTicker,
    *,
    count: int = 64,
    end: date = _AS_OF,
    volume: int = 1_000,
) -> PublicBarSeries:
    offset = Decimal(PUBLIC_REQUEST_TICKERS.index(ticker))
    slope = Decimal("0.15") + offset * Decimal("0.02")
    points = []
    for index, day in enumerate(_trading_dates(count, end=end)):
        close = Decimal("100") + offset + Decimal(index) * slope
        points.append(
            PublicBarPoint(
                trading_date=day,
                open=close - Decimal("0.10"),
                high=close + Decimal("0.50"),
                low=close - Decimal("0.50"),
                close=close,
                volume=volume + index,
            )
        )
    return PublicBarSeries(
        ticker=ticker,
        points=tuple(points),
        first_date=points[0].trading_date,
        latest_date=points[-1].trading_date,
    )


def _parsed(
    *,
    sector_tickers: tuple[SectorTicker, ...] = PUBLIC_SUPPORTED_SECTOR_TICKERS,
    count: int = 64,
    end: date = _AS_OF,
    volume: int = 1_000,
) -> PublicParsedSet:
    failures = tuple(
        PublicSourceFailure(
            ticker=ticker,
            issue_code=PublicSourceIssueCode.TRANSPORT,
            retryable=True,
        )
        for ticker in PUBLIC_SUPPORTED_SECTOR_TICKERS
        if ticker not in sector_tickers
    )
    return PublicParsedSet(
        benchmark=_bars(BENCHMARK_TICKER, count=count, end=end, volume=volume),
        sectors={
            ticker: _bars(ticker, count=count, end=end, volume=volume) for ticker in sector_tickers
        },
        failures=failures,
    )


def test_freshness_uses_versioned_nyse_calendar_and_fails_unknown_outside_it() -> None:
    assert resolve_public_freshness(_AS_OF, target_date=_AS_OF) is FreshnessState.FRESH
    assert (
        resolve_public_freshness(date(2026, 9, 4), target_date=date(2026, 9, 7))
        is FreshnessState.FRESH
    )
    assert resolve_public_freshness(date(2026, 8, 28), target_date=_AS_OF) is FreshnessState.STALE
    assert (
        resolve_public_freshness(date(2027, 1, 4), target_date=date(2027, 1, 4))
        is FreshnessState.UNKNOWN
    )


def test_build_bundle_is_close_only_partial_and_complete_provenance() -> None:
    bundle = build_public_series_bundle(_parsed(), target_date=_AS_OF)

    assert bundle.coverage.status is SectorCoverageStatus.PARTIAL
    assert bundle.coverage.available_sector_count == 10
    assert bundle.coverage.missing_tickers == (SectorTicker.XLRE,)
    assert bundle.coverage.reason_codes == (PublicDiagnosticCode.PROVIDER_UNAVAILABLE,)
    assert bundle.benchmark is not None
    assert len(bundle.benchmark.points) == 64
    assert bundle.failures == ()
    assert bundle.provenance.market_scope is MarketScope.IEX_VENUE_SAMPLE
    assert bundle.provenance.attributions == REQUIRED_PUBLIC_ATTRIBUTIONS
    assert bundle.provenance.target_date == _AS_OF
    assert bundle.provenance.as_of_date == _AS_OF

    serialized = bundle.model_dump_json()
    for forbidden in ('"open"', '"high"', '"low"', '"close"', '"volume"'):
        assert forbidden not in serialized


def test_full_snapshot_has_price_metrics_regime_rank_and_deterministic_id() -> None:
    bundle = build_public_series_bundle(_parsed(), target_date=_AS_OF)
    first = compute_public_sector_snapshot(bundle)
    second = compute_public_sector_snapshot(bundle)

    assert first == second
    assert first.snapshot_id is not None
    assert first.snapshot_id.startswith("sha256:")
    canonical = json.dumps(
        first.model_dump(mode="json", exclude={"snapshot_id"}),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    assert first.snapshot_id == f"sha256:{hashlib.sha256(canonical).hexdigest()}"
    assert first.freshness is FreshnessState.FRESH
    assert len(first.records) == 11
    comparable = [record for record in first.records if record.ticker is not SectorTicker.XLRE]
    assert all(record.availability is SectorAvailability.AVAILABLE for record in comparable)
    assert all(record.metrics.iex_price_return_63d.value is not None for record in comparable)
    assert all(
        record.primary_regime.regime is not SectorRegime.INSUFFICIENT for record in comparable
    )
    assert {record.relative_rank.ordinal for record in comparable} == set(range(1, 11))
    assert all(record.relative_rank.comparable_sector_count == 10 for record in comparable)

    xlre = next(record for record in first.records if record.ticker is SectorTicker.XLRE)
    assert xlre.availability is SectorAvailability.PROVIDER_UNAVAILABLE
    assert xlre.primary_regime.regime is SectorRegime.INSUFFICIENT
    assert xlre.relative_rank.score is None
    assert all(value.value is None for name, value in xlre.metrics if name != "ticker")


def test_changed_ohlcv_with_identical_closes_cannot_change_bundle_or_snapshot() -> None:
    ordinary = _parsed(volume=1_000)
    adversarial = _parsed(volume=9_000_000)

    ordinary_bundle = build_public_series_bundle(ordinary, target_date=_AS_OF)
    adversarial_bundle = build_public_series_bundle(adversarial, target_date=_AS_OF)
    assert ordinary_bundle == adversarial_bundle
    assert compute_public_sector_snapshot(ordinary_bundle) == compute_public_sector_snapshot(
        adversarial_bundle
    )


def test_source_file_never_reads_ohlcv_fields_other_than_close_conversion() -> None:
    tree = ast.parse(inspect.getsource(public_metrics))
    accessed = {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr in {"open", "high", "low", "volume"}
    }
    assert accessed == set()


def test_calendar_gap_becomes_explicit_ticker_failure_without_erasing_siblings() -> None:
    parsed = _parsed()
    xlb = parsed.sectors[SectorTicker.XLB]
    points = tuple(point for index, point in enumerate(xlb.points) if index != 20)
    gapped = PublicBarSeries(
        ticker=SectorTicker.XLB,
        points=points,
        first_date=points[0].trading_date,
        latest_date=points[-1].trading_date,
    )
    sectors = dict(parsed.sectors)
    sectors[SectorTicker.XLB] = gapped
    bundle = build_public_series_bundle(
        PublicParsedSet(benchmark=parsed.benchmark, sectors=sectors),
        target_date=_AS_OF,
    )

    assert bundle.coverage.status is SectorCoverageStatus.PARTIAL
    assert bundle.coverage.available_sector_count == 9
    failure = next(item for item in bundle.failures if item.ticker is SectorTicker.XLB)
    assert failure.issue_code is PublicSourceIssueCode.CALENDAR
    snapshot = compute_public_sector_snapshot(bundle)
    xlb_record = next(record for record in snapshot.records if record.ticker is SectorTicker.XLB)
    assert xlb_record.availability is SectorAvailability.TEMPORARILY_UNAVAILABLE
    assert PublicDiagnosticCode.TEMPORARILY_UNAVAILABLE in xlb_record.diagnostic_codes
    assert (
        xlb_record.metrics.iex_price_return_1d.missing_reason
        is MetricMissingReason.SECTOR_DATE_MISSING
    )
    assert xlb_record.primary_regime.missing_reason is MetricMissingReason.SECTOR_DATE_MISSING
    assert xlb_record.relative_rank.missing_reason == "sector_date_missing"


def test_fewer_than_eight_comparable_sectors_suppresses_every_metric_and_rank() -> None:
    bundle = build_public_series_bundle(
        _parsed(sector_tickers=PUBLIC_SUPPORTED_SECTOR_TICKERS[:7]),
        target_date=_AS_OF,
    )
    snapshot = compute_public_sector_snapshot(bundle)

    assert bundle.coverage.status is SectorCoverageStatus.INSUFFICIENT
    assert all(
        value.value is None
        for record in snapshot.records
        for name, value in record.metrics
        if name != "ticker"
    )
    assert all(record.relative_rank.score is None for record in snapshot.records)
    assert all(
        record.primary_regime.regime is SectorRegime.INSUFFICIENT for record in snapshot.records
    )


def test_warming_up_exposes_only_short_metrics_with_explicit_reasons() -> None:
    bundle = build_public_series_bundle(_parsed(count=20), target_date=_AS_OF)
    snapshot = compute_public_sector_snapshot(bundle)
    xlk = next(record for record in snapshot.records if record.ticker is SectorTicker.XLK)

    assert bundle.coverage.status is SectorCoverageStatus.WARMING_UP
    assert xlk.metrics.iex_price_return_1d.value is not None
    assert xlk.metrics.iex_price_return_5d.value is not None
    assert xlk.metrics.iex_price_return_21d.missing_reason is MetricMissingReason.WARMING_UP
    assert xlk.metrics.iex_price_excess_63d.missing_reason is MetricMissingReason.WARMING_UP
    assert xlk.metrics.iex_price_relative_acceleration_5d.missing_reason is (
        MetricMissingReason.WARMING_UP
    )
    assert xlk.primary_regime.missing_reason is MetricMissingReason.WARMING_UP
    assert xlk.relative_rank.missing_reason == "warming_up"


def test_stale_benchmark_forces_insufficient_snapshot_without_advancing_target() -> None:
    stale_as_of = date(2026, 8, 28)
    bundle = build_public_series_bundle(
        _parsed(end=stale_as_of),
        target_date=_AS_OF,
    )
    snapshot = compute_public_sector_snapshot(bundle)

    assert bundle.as_of_date == stale_as_of
    assert bundle.coverage.status is SectorCoverageStatus.INSUFFICIENT
    assert snapshot.freshness is FreshnessState.STALE
    assert snapshot.as_of_date == stale_as_of
    assert all(record.relative_rank.score is None for record in snapshot.records)


def test_non_fresh_bundle_cannot_be_relabelled_partial_to_publish_rank_or_regime() -> None:
    stale_bundle = build_public_series_bundle(
        _parsed(end=date(2026, 8, 28)),
        target_date=_AS_OF,
    )
    payload = stale_bundle.model_dump(mode="json")
    payload["coverage"]["status"] = SectorCoverageStatus.PARTIAL.value
    manipulated = type(stale_bundle).model_validate(payload)

    with pytest.raises(ValueError, match="non-fresh"):
        compute_public_sector_snapshot(manipulated)

    fresh = compute_public_sector_snapshot(
        build_public_series_bundle(_parsed(), target_date=_AS_OF)
    )
    snapshot_payload = fresh.model_dump(mode="json")
    snapshot_payload["freshness"] = FreshnessState.STALE.value
    with pytest.raises(ValueError, match="non-fresh"):
        type(fresh).model_validate(snapshot_payload)


def test_missing_benchmark_is_closed_and_preserves_no_metric_input() -> None:
    parsed = PublicParsedSet(
        failures=tuple(
            PublicSourceFailure(
                ticker=ticker,
                issue_code=PublicSourceIssueCode.AUTH_REJECTED,
                retryable=False,
            )
            for ticker in PUBLIC_REQUEST_TICKERS
        )
    )
    bundle = build_public_series_bundle(parsed, target_date=_AS_OF)
    snapshot = compute_public_sector_snapshot(bundle)

    assert bundle.benchmark is None
    assert bundle.sectors == ()
    assert bundle.as_of_date is None
    assert bundle.coverage.status is SectorCoverageStatus.INSUFFICIENT
    assert PublicDiagnosticCode.BENCHMARK_UNAVAILABLE in bundle.coverage.reason_codes
    assert snapshot.freshness is FreshnessState.UNKNOWN
    assert all(record.metrics.iex_price_return_1d.value is None for record in snapshot.records)


def test_metric_wrapper_uses_simple_price_return_and_simple_realized_volatility() -> None:
    bundle = build_public_series_bundle(_parsed(), target_date=_AS_OF)
    assert bundle.benchmark is not None
    sector = next(series for series in bundle.sectors if series.ticker is SectorTicker.XLK)
    metrics = compute_public_sector_metrics(
        sector,
        bundle.benchmark,
        coverage_status=SectorCoverageStatus.PARTIAL,
        target_date=_AS_OF,
    )

    expected = sector.points[-1].value / sector.points[-2].value - Decimal(1)
    assert metrics.iex_price_return_1d.value == expected.quantize(Decimal("0.0000000001"))
    assert metrics.iex_price_realized_volatility_20d.value is not None
    assert metrics.iex_price_realized_volatility_20d.value >= 0


def test_target_date_rejects_non_date_values() -> None:
    with pytest.raises(ValueError, match="date-only"):
        build_public_series_bundle(_parsed(), target_date=None)  # type: ignore[arg-type]


def test_fixed_record_order_is_independent_of_input_mapping_order() -> None:
    parsed = _parsed()
    reversed_parsed = PublicParsedSet(
        benchmark=parsed.benchmark,
        sectors=dict(reversed(tuple(parsed.sectors.items()))),
    )
    ordinary = compute_public_sector_snapshot(
        build_public_series_bundle(parsed, target_date=_AS_OF)
    )
    reversed_snapshot = compute_public_sector_snapshot(
        build_public_series_bundle(reversed_parsed, target_date=_AS_OF)
    )

    assert tuple(record.ticker for record in ordinary.records) == SECTOR_TICKERS
    assert reversed_snapshot == ordinary
