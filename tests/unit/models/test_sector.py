"""u139 typed sector-domain contract tests (FD E1-E21)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from investo.models import (
    ALL_SECTOR_TICKERS,
    BENCHMARK_TICKER,
    FIXED_SECTOR_UNIVERSE,
    PRIMARY_REGIME_POLICY,
    REGIME_BANDS_BPS,
    SECTOR_TICKERS,
    AxisState,
    CoverageSummary,
    DiagnosticIssueCode,
    MetricMissingReason,
    MetricValue,
    NavPoint,
    NavSeries,
    ParsedWorkbookSet,
    PrivateArtifactSet,
    PrivateDiagnostic,
    PrivateWorkbookManifest,
    RegimeResult,
    RelativeRank,
    SectorCoverageStatus,
    SectorDashboardSnapshot,
    SectorMetricName,
    SectorMetrics,
    SectorRecord,
    SectorRegime,
    SectorSeriesBundle,
    SectorTicker,
    SectorUniverse,
    WorkbookFailure,
    WorkbookIssueCode,
)

PBT_SETTINGS = settings(max_examples=50, deadline=None)
_AS_OF = date(2026, 7, 17)


def _missing(
    reason: MetricMissingReason = MetricMissingReason.COVERAGE_INSUFFICIENT,
) -> MetricValue:
    return MetricValue(missing_reason=reason)


def _metrics(
    ticker: SectorTicker,
    *,
    nav_return_1d: MetricValue | None = None,
) -> SectorMetrics:
    missing = _missing()
    return SectorMetrics(
        ticker=ticker,
        nav_return_1d=nav_return_1d or missing,
        nav_return_5d=missing,
        nav_return_21d=missing,
        nav_return_63d=missing,
        nav_excess_1d=missing,
        nav_excess_5d=missing,
        nav_excess_21d=missing,
        nav_excess_63d=missing,
        nav_relative_acceleration_5d=missing,
        nav_realized_volatility_20d=missing,
        nav_max_drawdown_20d=missing,
    )


def _record(
    ticker: SectorTicker,
    *,
    score: Decimal | None = None,
    ordinal: int | None = None,
    nav_return_1d: MetricValue | None = None,
) -> SectorRecord:
    if score is None:
        regime = RegimeResult(
            ticker=ticker,
            regime=SectorRegime.INSUFFICIENT,
            policy_id=PRIMARY_REGIME_POLICY.policy_id,
            missing_reason=MetricMissingReason.COVERAGE_INSUFFICIENT,
        )
        rank = RelativeRank(
            comparable_sector_count=0,
            missing_reason="coverage_insufficient",
        )
    else:
        regime = RegimeResult(
            ticker=ticker,
            regime=SectorRegime.LEADING,
            strength_state=AxisState.POSITIVE,
            acceleration_state=AxisState.POSITIVE,
            policy_id=PRIMARY_REGIME_POLICY.policy_id,
        )
        rank = RelativeRank(
            score=score,
            ordinal=ordinal,
            comparable_sector_count=11,
            used_horizons=(63, 5, 21),
        )
    return SectorRecord(
        ticker=ticker,
        metrics=_metrics(ticker, nav_return_1d=nav_return_1d),
        primary_regime=regime,
        sensitivity_regimes={band: regime.regime for band in reversed(REGIME_BANDS_BPS)},
        relative_rank=rank,
    )


def _insufficient_coverage() -> CoverageSummary:
    return CoverageSummary(
        status=SectorCoverageStatus.INSUFFICIENT,
        available_sector_count=0,
        benchmark_available=False,
        benchmark_observation_count=0,
        missing_tickers=tuple(reversed(SECTOR_TICKERS)),
        reason_codes=(
            DiagnosticIssueCode.BUNDLE_COVERAGE_INSUFFICIENT,
            DiagnosticIssueCode.BUNDLE_SPY_MISSING,
        ),
    )


def _insufficient_snapshot(
    order: tuple[SectorTicker, ...] = SECTOR_TICKERS,
) -> SectorDashboardSnapshot:
    return SectorDashboardSnapshot(
        coverage=_insufficient_coverage(),
        records=tuple(_record(ticker) for ticker in order),
        diagnostics=(
            PrivateDiagnostic(issue_code=DiagnosticIssueCode.BUNDLE_SPY_MISSING),
            PrivateDiagnostic(issue_code=DiagnosticIssueCode.BUNDLE_COVERAGE_INSUFFICIENT),
        ),
        input_fingerprint="sha256:" + "a" * 64,
    )


def _series(ticker: SectorTicker, *, start: date = date(2026, 7, 16)) -> NavSeries:
    points = (
        NavPoint(trading_date=start, nav=Decimal("100.1")),
        NavPoint(trading_date=start + timedelta(days=1), nav=Decimal("101.2")),
    )
    return NavSeries(
        ticker=ticker,
        points=points,
        first_date=points[0].trading_date,
        latest_date=points[-1].trading_date,
    )


def test_fixed_universe_identity_and_order() -> None:
    assert tuple(ticker.value for ticker in SECTOR_TICKERS) == (
        "XLC",
        "XLY",
        "XLP",
        "XLE",
        "XLF",
        "XLV",
        "XLI",
        "XLB",
        "XLRE",
        "XLK",
        "XLU",
    )
    assert (*SECTOR_TICKERS, SectorTicker.SPY) == ALL_SECTOR_TICKERS
    assert BENCHMARK_TICKER is SectorTicker.SPY
    assert SectorUniverse() == FIXED_SECTOR_UNIVERSE


def test_universe_rejects_alias_or_reordering() -> None:
    with pytest.raises(ValueError):
        SectorTicker("xlk")
    with pytest.raises(ValidationError):
        SectorUniverse(sectors=tuple(reversed(SECTOR_TICKERS)))


def test_manifest_requires_exact_absolute_unique_xlsx_paths() -> None:
    mapping = {
        ticker: Path(f"/private/sector/{ticker.value.lower()}.xlsx")
        for ticker in reversed(ALL_SECTOR_TICKERS)
    }
    manifest = PrivateWorkbookManifest(schema_version=1, workbooks=mapping)

    assert tuple(manifest.workbooks) == ALL_SECTOR_TICKERS
    assert PrivateWorkbookManifest.model_validate_json(manifest.model_dump_json()) == manifest
    with pytest.raises(TypeError):
        manifest.workbooks[SectorTicker.XLC] = Path("/private/other.xlsx")  # type: ignore[index]

    with pytest.raises(ValidationError):
        PrivateWorkbookManifest(
            schema_version=1, workbooks={SectorTicker.SPY: mapping[SectorTicker.SPY]}
        )
    mapping[SectorTicker.XLC] = mapping[SectorTicker.XLY]
    with pytest.raises(ValidationError):
        PrivateWorkbookManifest(schema_version=1, workbooks=mapping)


@pytest.mark.parametrize("invalid", [Decimal("0"), Decimal("-1"), Decimal("NaN"), True])
def test_nav_point_rejects_invalid_domain(invalid: Decimal | bool) -> None:
    with pytest.raises(ValidationError):
        NavPoint(trading_date=_AS_OF, nav=invalid)


def test_nav_point_rejects_datetime_shaped_date_strings() -> None:
    with pytest.raises(ValidationError, match="YYYY-MM-DD"):
        NavPoint(trading_date="2026-07-17T00:00:00Z", nav=Decimal("100"))


def test_nav_series_rejects_duplicate_or_wrong_endpoint() -> None:
    point = NavPoint(trading_date=_AS_OF, nav=Decimal("100"))
    with pytest.raises(ValidationError):
        NavSeries(
            ticker=SectorTicker.XLC,
            points=(point, point),
            first_date=_AS_OF,
            latest_date=_AS_OF,
        )
    with pytest.raises(ValidationError):
        NavSeries(
            ticker=SectorTicker.XLC,
            points=_series(SectorTicker.XLC).points,
            first_date=_AS_OF,
            latest_date=_AS_OF,
        )


def test_parsed_workbook_set_partitions_all_identities_and_orders_failures() -> None:
    success = _series(SectorTicker.XLC)
    failures = tuple(
        WorkbookFailure(ticker=ticker, issue_code=WorkbookIssueCode.OPEN)
        for ticker in reversed(ALL_SECTOR_TICKERS)
        if ticker is not SectorTicker.XLC
    )
    parsed = ParsedWorkbookSet(
        series_by_ticker={SectorTicker.XLC: success},
        failures=failures,
    )

    assert tuple(parsed.series_by_ticker) == (SectorTicker.XLC,)
    assert tuple(failure.ticker for failure in parsed.failures) == ALL_SECTOR_TICKERS[1:]
    assert ParsedWorkbookSet.model_validate_json(parsed.model_dump_json()) == parsed
    with pytest.raises(TypeError):
        parsed.series_by_ticker[SectorTicker.XLY] = _series(SectorTicker.XLY)  # type: ignore[index]

    with pytest.raises(ValidationError):
        ParsedWorkbookSet(series_by_ticker={SectorTicker.XLC: success}, failures=())


def test_series_bundle_cross_checks_coverage_against_canonical_series() -> None:
    sector = _series(SectorTicker.XLC)
    benchmark = _series(SectorTicker.SPY)
    coverage = CoverageSummary(
        status=SectorCoverageStatus.INSUFFICIENT,
        available_sector_count=1,
        benchmark_available=True,
        common_as_of=benchmark.latest_date,
        benchmark_observation_count=len(benchmark.points),
        missing_tickers=SECTOR_TICKERS[1:],
    )

    bundle = SectorSeriesBundle(
        as_of_date=benchmark.latest_date,
        benchmark=benchmark,
        sectors=(sector,),
        coverage=coverage,
    )

    assert bundle.sectors == (sector,)
    with pytest.raises(ValidationError, match="benchmark count"):
        SectorSeriesBundle(
            as_of_date=benchmark.latest_date,
            benchmark=benchmark,
            sectors=(sector,),
            coverage=coverage.model_copy(update={"benchmark_observation_count": 3}),
        )


def test_coverage_normalizes_missing_and_reasons() -> None:
    coverage = _insufficient_coverage()

    assert coverage.missing_tickers == SECTOR_TICKERS
    assert coverage.reason_codes == tuple(sorted(coverage.reason_codes, key=str))

    with pytest.raises(ValidationError):
        CoverageSummary(
            status=SectorCoverageStatus.NORMAL,
            available_sector_count=11,
            benchmark_available=True,
            common_as_of=_AS_OF,
            benchmark_observation_count=21,
        )


def test_metric_value_is_exclusive_quantized_and_normalizes_negative_zero() -> None:
    value = MetricValue(value=Decimal("1.23456789015"))
    negative_zero = MetricValue(value=Decimal("-0.00000000001"))

    assert value.value == Decimal("1.2345678902")
    assert negative_zero.value == Decimal("0.0000000000")
    with pytest.raises(ValidationError):
        MetricValue()
    with pytest.raises(ValidationError):
        MetricValue(value=Decimal("1"), missing_reason=MetricMissingReason.NUMERIC_INVALID)


@pytest.mark.parametrize(
    ("strength", "acceleration", "regime"),
    [
        (AxisState.POSITIVE, AxisState.POSITIVE, SectorRegime.LEADING),
        (AxisState.POSITIVE, AxisState.NEGATIVE, SectorRegime.WEAKENING),
        (AxisState.NEGATIVE, AxisState.POSITIVE, SectorRegime.RECOVERING),
        (AxisState.NEGATIVE, AxisState.NEGATIVE, SectorRegime.LAGGING),
    ],
)
def test_regime_matches_each_axis_state_pair(
    strength: AxisState,
    acceleration: AxisState,
    regime: SectorRegime,
) -> None:
    result = RegimeResult(
        ticker=SectorTicker.XLK,
        regime=regime,
        strength_state=strength,
        acceleration_state=acceleration,
        policy_id=PRIMARY_REGIME_POLICY.policy_id,
    )

    assert result.regime is regime


def test_regime_rejects_mismatched_axis_states() -> None:
    with pytest.raises(ValidationError, match="must match"):
        RegimeResult(
            ticker=SectorTicker.XLK,
            regime=SectorRegime.LEADING,
            strength_state=AxisState.NEGATIVE,
            acceleration_state=AxisState.NEGATIVE,
            policy_id=PRIMARY_REGIME_POLICY.policy_id,
        )


def test_rank_and_record_normalize_horizons_sensitivity_and_snapshot_order() -> None:
    high = _record(SectorTicker.XLK, score=Decimal("0.9"), ordinal=1)
    low = _record(SectorTicker.XLE, score=Decimal("0.1"), ordinal=2)
    missing = tuple(
        _record(ticker)
        for ticker in SECTOR_TICKERS
        if ticker not in {SectorTicker.XLK, SectorTicker.XLE}
    )
    coverage = CoverageSummary(
        status=SectorCoverageStatus.NORMAL,
        available_sector_count=11,
        benchmark_available=True,
        common_as_of=_AS_OF,
        benchmark_observation_count=64,
    )
    snapshot = SectorDashboardSnapshot(
        as_of_date=_AS_OF,
        coverage=coverage,
        records=(low, *missing, high),
    )

    assert high.relative_rank.used_horizons == (5, 21, 63)
    assert tuple(high.sensitivity_regimes) == REGIME_BANDS_BPS
    assert snapshot.records[:2] == (high, low)
    with pytest.raises(TypeError):
        high.sensitivity_regimes[10] = SectorRegime.LAGGING  # type: ignore[index]


def test_insufficient_snapshot_rejects_metric_leakage() -> None:
    leaking = _record(
        SectorTicker.XLC,
        nav_return_1d=MetricValue(value=Decimal("0.01")),
    )
    records = (leaking, *tuple(_record(ticker) for ticker in SECTOR_TICKERS[1:]))

    with pytest.raises(ValidationError):
        SectorDashboardSnapshot(coverage=_insufficient_coverage(), records=records)


def test_partial_snapshot_suppresses_unavailable_sector_claims() -> None:
    missing_tickers = SECTOR_TICKERS[8:]
    coverage = CoverageSummary(
        status=SectorCoverageStatus.PARTIAL,
        available_sector_count=8,
        benchmark_available=True,
        common_as_of=_AS_OF,
        benchmark_observation_count=22,
        missing_tickers=missing_tickers,
    )
    records = tuple(
        _record(
            ticker,
            score=Decimal("0.9") if ticker is missing_tickers[0] else None,
            ordinal=1 if ticker is missing_tickers[0] else None,
            nav_return_1d=(
                MetricValue(value=Decimal("0.01")) if ticker is missing_tickers[0] else None
            ),
        )
        for ticker in SECTOR_TICKERS
    )

    with pytest.raises(ValidationError, match="missing sectors"):
        SectorDashboardSnapshot(as_of_date=_AS_OF, coverage=coverage, records=records)


def test_private_diagnostic_accepts_only_closed_metric_identifiers() -> None:
    diagnostic = PrivateDiagnostic(
        issue_code=DiagnosticIssueCode.METRIC_INSUFFICIENT_HISTORY,
        ticker=SectorTicker.XLK,
        metric_name=SectorMetricName.NAV_EXCESS_63D,
    )

    assert diagnostic.metric_name is SectorMetricName.NAV_EXCESS_63D
    with pytest.raises(ValidationError):
        PrivateDiagnostic(
            issue_code=DiagnosticIssueCode.METRIC_INSUFFICIENT_HISTORY,
            metric_name="/Users/operator/private/nav.xlsx",
        )


def test_snapshot_reserves_validated_projection_integrity_field() -> None:
    snapshot = _insufficient_snapshot()
    invalid_payload = snapshot.model_dump()
    invalid_payload["snapshot_id"] = "sha256:not-a-digest"

    assert tuple(snapshot.model_dump())[:2] == ("schema_version", "snapshot_id")
    with pytest.raises(ValidationError):
        SectorDashboardSnapshot.model_validate(invalid_payload)


def test_private_artifact_set_requires_exact_absolute_pair() -> None:
    artifact_set = PrivateArtifactSet(
        snapshot_path=Path("/private/output/snapshot.json"),
        report_path=Path("/private/output/report.md"),
    )

    assert artifact_set.snapshot_path.parent == artifact_set.report_path.parent
    with pytest.raises(ValidationError):
        PrivateArtifactSet(
            snapshot_path=Path("snapshot.json"),
            report_path=Path("report.md"),
        )


@given(
    values=st.lists(
        st.decimals(
            min_value=Decimal("0.0001"),
            max_value=Decimal("1000000"),
            allow_nan=False,
            allow_infinity=False,
            places=8,
        ),
        min_size=2,
        max_size=30,
    ),
    start=st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 1, 1)),
)
@PBT_SETTINGS
def test_nav_series_json_round_trip(values: list[Decimal], start: date) -> None:
    points = tuple(
        NavPoint(trading_date=start + timedelta(days=index), nav=value)
        for index, value in enumerate(values)
    )
    series = NavSeries(
        ticker=SectorTicker.XLK,
        points=points,
        first_date=points[0].trading_date,
        latest_date=points[-1].trading_date,
    )

    assert NavSeries.model_validate_json(series.model_dump_json()) == series


@given(order=st.permutations(SECTOR_TICKERS))
@PBT_SETTINGS
def test_snapshot_json_round_trip_and_order_are_stable(order: list[SectorTicker]) -> None:
    snapshot = _insufficient_snapshot(tuple(order))
    reference = _insufficient_snapshot()

    assert tuple(record.ticker for record in snapshot.records) == SECTOR_TICKERS
    assert snapshot.model_dump_json() == reference.model_dump_json()
    assert SectorDashboardSnapshot.model_validate_json(snapshot.model_dump_json()) == snapshot


@given(
    value=st.decimals(
        min_value=Decimal("-1000000"),
        max_value=Decimal("1000000"),
        allow_nan=False,
        allow_infinity=False,
        places=12,
    )
)
@PBT_SETTINGS
def test_metric_quantization_is_idempotent(value: Decimal) -> None:
    once = MetricValue(value=value)
    twice = MetricValue(value=once.value)

    assert twice == once
