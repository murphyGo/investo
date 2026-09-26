"""Derived-only snapshot computation for the limited public sector radar.

This module is the semantic boundary between validated HF/IEX bars and the
public aggregate model. It retains only dates and closes, computes through the
shared source-neutral kernels, and never exposes raw provider rows.
"""

from __future__ import annotations

import hashlib
import json
import statistics
from collections.abc import Callable, Mapping, Sequence
from datetime import date, datetime
from decimal import ROUND_HALF_EVEN, Decimal, DecimalException, localcontext
from typing import Final, Literal

from investo.models.market_calendar import is_trading_day, previous_trading_day
from investo.models.sector import (
    BENCHMARK_TICKER,
    PRIMARY_REGIME_POLICY,
    RANK_HORIZONS,
    SECTOR_TICKERS,
    MetricMissingReason,
    MetricValue,
    RankHorizon,
    RegimeResult,
    RelativeRank,
    SectorCoverageStatus,
    SectorTicker,
)
from investo.models.sector_public import (
    PUBLIC_SUPPORTED_SECTOR_TICKERS,
    FreshnessState,
    PublicBarSeries,
    PublicCoverageSummary,
    PublicDiagnosticCode,
    PublicParsedSet,
    PublicSectorDashboardSnapshot,
    PublicSectorMetrics,
    PublicSectorRecord,
    PublicSectorSeriesBundle,
    PublicSourceFailure,
    PublicSourceIssueCode,
    PublicSourceProvenance,
    SectorAvailability,
    ValuePoint,
    ValueSeries,
)
from investo.sector_dashboard.metric_kernels import (
    descending_midrank_percentiles,
    excess_return,
    max_drawdown_20d,
    realized_volatility_20d,
    relative_acceleration_5d,
    simple_return,
)
from investo.sector_dashboard.regime import classify_regime_history

MetricHorizon = Literal[1, 5, 21, 63]

_CALENDAR_YEAR: Final = 2026
_CALCULATION_OBSERVATIONS: Final = 64
_MIN_SHORT_OBSERVATIONS: Final = 6
_METRIC_HORIZONS: Final[tuple[MetricHorizon, ...]] = (1, 5, 21, 63)
_WARMING_HORIZONS: Final[frozenset[MetricHorizon]] = frozenset({1, 5})
_RANK_WEIGHTS: Final[dict[RankHorizon, Decimal]] = {
    5: Decimal("0.20"),
    21: Decimal("0.50"),
    63: Decimal("0.30"),
}


def resolve_public_freshness(as_of_date: date | None, *, target_date: date) -> FreshnessState:
    """Resolve freshness against the versioned NYSE calendar.

    ``target_date`` is the caller-resolved New York market date. The static
    calendar is authoritative only for 2026; dates outside that version fail
    closed as ``unknown`` instead of falling back to weekdays.
    """

    if isinstance(target_date, datetime) or not isinstance(target_date, date):
        raise ValueError("target_date must be date-only")
    if target_date.year != _CALENDAR_YEAR:
        return FreshnessState.UNKNOWN
    expected_session = (
        target_date
        if is_trading_day("us-equity", target_date)
        else previous_trading_day("us-equity", target_date)
    )
    if expected_session.year != _CALENDAR_YEAR or as_of_date is None:
        return FreshnessState.UNKNOWN
    if as_of_date == expected_session:
        return FreshnessState.FRESH
    if as_of_date < expected_session:
        return FreshnessState.STALE
    return FreshnessState.UNKNOWN


def build_public_series_bundle(
    parsed: PublicParsedSet,
    *,
    target_date: date,
) -> PublicSectorSeriesBundle:
    """Build the close-only, same-as-of bundle from one parsed HF collection."""

    if isinstance(target_date, datetime) or not isinstance(target_date, date):
        raise ValueError("target_date must be date-only")
    source_failures = {failure.ticker: failure for failure in parsed.failures}
    benchmark_bars = parsed.benchmark
    if benchmark_bars is None:
        benchmark_failure = source_failures.get(BENCHMARK_TICKER)
        fallback_issue = (
            benchmark_failure.issue_code
            if benchmark_failure is not None
            else PublicSourceIssueCode.TRANSPORT
        )
        fallback_retryable = benchmark_failure.retryable if benchmark_failure is not None else True
        failures = dict(source_failures)
        for ticker in parsed.sectors:
            failures[ticker] = PublicSourceFailure(
                ticker=ticker,
                issue_code=fallback_issue,
                retryable=fallback_retryable,
            )
        return _bundle(
            target_date=target_date,
            as_of_date=None,
            benchmark=None,
            sectors=(),
            failures=failures,
            freshness=FreshnessState.UNKNOWN,
        )

    as_of_date = benchmark_bars.latest_date
    if as_of_date > target_date:
        failures = dict(source_failures)
        failures[BENCHMARK_TICKER] = PublicSourceFailure(
            ticker=BENCHMARK_TICKER,
            issue_code=PublicSourceIssueCode.FRESHNESS,
            retryable=False,
        )
        for ticker in parsed.sectors:
            failures[ticker] = PublicSourceFailure(
                ticker=ticker,
                issue_code=PublicSourceIssueCode.FRESHNESS,
                retryable=False,
            )
        return _bundle(
            target_date=target_date,
            as_of_date=None,
            benchmark=None,
            sectors=(),
            failures=failures,
            freshness=FreshnessState.UNKNOWN,
        )

    benchmark = _close_series(benchmark_bars)
    benchmark_dates = tuple(point.trading_date for point in benchmark.points)
    required_count = (
        _CALCULATION_OBSERVATIONS
        if len(benchmark_dates) >= _CALCULATION_OBSERVATIONS
        else min(_MIN_SHORT_OBSERVATIONS, len(benchmark_dates))
    )
    required_dates = benchmark_dates[-required_count:]
    sectors: list[ValueSeries] = []
    failures = dict(source_failures)
    for ticker in PUBLIC_SUPPORTED_SECTOR_TICKERS:
        bars = parsed.sectors.get(ticker)
        if bars is None:
            continue
        close_by_date = {point.trading_date: point.close for point in bars.points}
        if as_of_date not in close_by_date or any(
            day not in close_by_date for day in required_dates
        ):
            failures[ticker] = PublicSourceFailure(
                ticker=ticker,
                issue_code=PublicSourceIssueCode.CALENDAR,
                retryable=False,
            )
            continue
        points = tuple(
            ValuePoint(trading_date=day, value=close_by_date[day])
            for day in benchmark_dates
            if day in close_by_date
        )
        if len(points) < 2:
            failures[ticker] = PublicSourceFailure(
                ticker=ticker,
                issue_code=PublicSourceIssueCode.INSUFFICIENT_HISTORY,
                retryable=False,
            )
            continue
        sectors.append(ValueSeries(ticker=ticker, points=points))

    return _bundle(
        target_date=target_date,
        as_of_date=as_of_date,
        benchmark=benchmark,
        sectors=tuple(sectors),
        failures=failures,
        freshness=resolve_public_freshness(as_of_date, target_date=target_date),
    )


def compute_public_sector_metrics(
    sector: ValueSeries,
    benchmark: ValueSeries,
    *,
    coverage_status: SectorCoverageStatus,
    target_date: date | None = None,
) -> PublicSectorMetrics:
    """Compute every public IEX-price metric slot for one sector."""

    if sector.ticker is BENCHMARK_TICKER:
        raise ValueError("public sector metrics cannot be computed for SPY")
    if benchmark.ticker is not BENCHMARK_TICKER:
        raise ValueError("public benchmark series must be SPY")
    if coverage_status is SectorCoverageStatus.INSUFFICIENT:
        return _missing_metrics(sector.ticker, MetricMissingReason.COVERAGE_INSUFFICIENT)

    benchmark_dates = tuple(point.trading_date for point in benchmark.points)
    requested_date = target_date or benchmark.latest_date
    try:
        target_index = benchmark_dates.index(requested_date)
    except ValueError:
        return _missing_metrics(sector.ticker, MetricMissingReason.BENCHMARK_DATE_MISSING)

    sector_values = {point.trading_date: point.value for point in sector.points}
    benchmark_values = {point.trading_date: point.value for point in benchmark.points}
    returns: dict[MetricHorizon, MetricValue] = {}
    excess: dict[MetricHorizon, MetricValue] = {}
    for horizon in _METRIC_HORIZONS:
        if coverage_status is SectorCoverageStatus.WARMING_UP and horizon not in _WARMING_HORIZONS:
            returns[horizon] = _missing(MetricMissingReason.WARMING_UP)
            excess[horizon] = _missing(MetricMissingReason.WARMING_UP)
        else:
            returns[horizon], excess[horizon] = _return_pair(
                horizon=horizon,
                target_index=target_index,
                benchmark_dates=benchmark_dates,
                sector_values=sector_values,
                benchmark_values=benchmark_values,
            )

    if coverage_status is SectorCoverageStatus.WARMING_UP:
        acceleration = _missing(MetricMissingReason.WARMING_UP)
        volatility = _missing(MetricMissingReason.WARMING_UP)
        drawdown = _missing(MetricMissingReason.WARMING_UP)
    else:
        acceleration = _acceleration_metric(
            target_index=target_index,
            benchmark_dates=benchmark_dates,
            sector_values=sector_values,
            benchmark_values=benchmark_values,
        )
        volatility = _window_metric(
            target_index=target_index,
            benchmark_dates=benchmark_dates,
            sector_values=sector_values,
            calculator=lambda values: realized_volatility_20d(values, return_kind="simple"),
        )
        drawdown = _window_metric(
            target_index=target_index,
            benchmark_dates=benchmark_dates,
            sector_values=sector_values,
            calculator=max_drawdown_20d,
        )

    return PublicSectorMetrics(
        ticker=sector.ticker,
        iex_price_return_1d=returns[1],
        iex_price_return_5d=returns[5],
        iex_price_return_21d=returns[21],
        iex_price_return_63d=returns[63],
        iex_price_excess_1d=excess[1],
        iex_price_excess_5d=excess[5],
        iex_price_excess_21d=excess[21],
        iex_price_excess_63d=excess[63],
        iex_price_relative_acceleration_5d=acceleration,
        iex_price_realized_volatility_20d=volatility,
        iex_price_max_drawdown_20d=drawdown,
    )


def compute_public_sector_snapshot(
    bundle: PublicSectorSeriesBundle,
) -> PublicSectorDashboardSnapshot:
    """Build an immutable, deterministic, derived-only public snapshot."""

    freshness = resolve_public_freshness(
        bundle.as_of_date,
        target_date=bundle.provenance.target_date,
    )
    if (
        freshness is not FreshnessState.FRESH
        and bundle.coverage.status is not SectorCoverageStatus.INSUFFICIENT
    ):
        raise ValueError("non-fresh public bundles must use insufficient coverage")
    benchmark = bundle.benchmark
    available = {series.ticker: series for series in bundle.sectors}
    failures = {failure.ticker: failure for failure in bundle.failures}
    metrics_by_ticker: dict[SectorTicker, PublicSectorMetrics] = {}
    for ticker in SECTOR_TICKERS:
        series = available.get(ticker)
        if benchmark is None or series is None:
            reason = _metric_reason_for_failure(failures.get(ticker))
            metrics_by_ticker[ticker] = _missing_metrics(ticker, reason)
        else:
            metrics_by_ticker[ticker] = compute_public_sector_metrics(
                series,
                benchmark,
                coverage_status=bundle.coverage.status,
                target_date=bundle.as_of_date,
            )

    ranks = _compute_public_ranks(
        available,
        benchmark,
        metrics_by_ticker,
        coverage_status=bundle.coverage.status,
        target_date=bundle.as_of_date,
    )
    records: list[PublicSectorRecord] = []
    for ticker in SECTOR_TICKERS:
        series = available.get(ticker)
        failure = failures.get(ticker)
        metrics = metrics_by_ticker[ticker]
        availability, diagnostic_codes = _availability(ticker, series, failure)
        regime = _compute_public_regime(
            ticker=ticker,
            sector=series,
            benchmark=benchmark,
            metrics=metrics,
            coverage_status=bundle.coverage.status,
            target_date=bundle.as_of_date,
        )
        if any(
            metric.missing_reason is MetricMissingReason.INSUFFICIENT_HISTORY
            for name, metric in metrics
            if name != "ticker"
        ):
            diagnostic_codes = (*diagnostic_codes, PublicDiagnosticCode.METRIC_INSUFFICIENT_HISTORY)
        records.append(
            PublicSectorRecord(
                ticker=ticker,
                availability=availability,
                metrics=metrics,
                primary_regime=regime,
                relative_rank=ranks[ticker],
                diagnostic_codes=diagnostic_codes,
            )
        )

    base = PublicSectorDashboardSnapshot(
        as_of_date=bundle.as_of_date,
        freshness=freshness,
        coverage=bundle.coverage,
        records=tuple(records),
        provenance=bundle.provenance,
    )
    payload = base.model_dump(mode="json", exclude={"snapshot_id"})
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    snapshot_id = f"sha256:{hashlib.sha256(canonical).hexdigest()}"
    return PublicSectorDashboardSnapshot.model_validate({**payload, "snapshot_id": snapshot_id})


def _bundle(
    *,
    target_date: date,
    as_of_date: date | None,
    benchmark: ValueSeries | None,
    sectors: tuple[ValueSeries, ...],
    failures: Mapping[SectorTicker, PublicSourceFailure],
    freshness: FreshnessState,
) -> PublicSectorSeriesBundle:
    available = {series.ticker for series in sectors}
    missing = tuple(ticker for ticker in SECTOR_TICKERS if ticker not in available)
    benchmark_count = len(benchmark.points) if benchmark is not None else 0
    status = _coverage_status(
        benchmark_available=benchmark is not None,
        benchmark_count=benchmark_count,
        available_count=len(sectors),
        freshness=freshness,
    )
    reason_codes: list[PublicDiagnosticCode] = [PublicDiagnosticCode.PROVIDER_UNAVAILABLE]
    if benchmark is None or freshness is not FreshnessState.FRESH:
        reason_codes.append(PublicDiagnosticCode.BENCHMARK_UNAVAILABLE)
    if status is SectorCoverageStatus.WARMING_UP or benchmark_count < _CALCULATION_OBSERVATIONS:
        reason_codes.append(PublicDiagnosticCode.INSUFFICIENT_HISTORY)
    if any(
        failure.issue_code is not PublicSourceIssueCode.INSUFFICIENT_HISTORY
        for ticker, failure in failures.items()
        if ticker is not BENCHMARK_TICKER
    ):
        reason_codes.append(PublicDiagnosticCode.TEMPORARILY_UNAVAILABLE)
    coverage = PublicCoverageSummary(
        status=status,
        available_sector_count=len(sectors),
        benchmark_available=benchmark is not None,
        common_as_of=as_of_date,
        benchmark_observation_count=benchmark_count,
        missing_tickers=missing,
        reason_codes=tuple(reason_codes),
    )
    provenance = PublicSourceProvenance(target_date=target_date, as_of_date=as_of_date)
    return PublicSectorSeriesBundle(
        as_of_date=as_of_date,
        benchmark=benchmark,
        sectors=sectors,
        coverage=coverage,
        failures=tuple(failures.values()),
        provenance=provenance,
    )


def _coverage_status(
    *,
    benchmark_available: bool,
    benchmark_count: int,
    available_count: int,
    freshness: FreshnessState,
) -> SectorCoverageStatus:
    if (
        not benchmark_available
        or freshness is not FreshnessState.FRESH
        or available_count < 8
        or benchmark_count < _MIN_SHORT_OBSERVATIONS
    ):
        return SectorCoverageStatus.INSUFFICIENT
    if benchmark_count < _CALCULATION_OBSERVATIONS:
        return SectorCoverageStatus.WARMING_UP
    if available_count == 11:
        return SectorCoverageStatus.NORMAL
    return SectorCoverageStatus.PARTIAL


def _close_series(bars: PublicBarSeries) -> ValueSeries:
    points = bars.points[-_CALCULATION_OBSERVATIONS:]
    return ValueSeries(
        ticker=bars.ticker,
        points=tuple(
            ValuePoint(trading_date=point.trading_date, value=point.close) for point in points
        ),
    )


def _return_pair(
    *,
    horizon: MetricHorizon,
    target_index: int,
    benchmark_dates: Sequence[date],
    sector_values: Mapping[date, Decimal],
    benchmark_values: Mapping[date, Decimal],
) -> tuple[MetricValue, MetricValue]:
    if target_index < horizon:
        missing = _missing(MetricMissingReason.INSUFFICIENT_HISTORY)
        return missing, missing
    required_dates = benchmark_dates[target_index - horizon : target_index + 1]
    if any(day not in sector_values for day in required_dates):
        missing = _missing(MetricMissingReason.SECTOR_DATE_MISSING)
        return missing, missing
    start_date, end_date = required_dates[0], required_dates[-1]
    try:
        subject_return = simple_return(sector_values[start_date], sector_values[end_date])
        subject_excess = excess_return(
            sector_values[start_date],
            sector_values[end_date],
            benchmark_values[start_date],
            benchmark_values[end_date],
        )
        return MetricValue(value=subject_return), MetricValue(value=subject_excess)
    except (DecimalException, OverflowError, ValueError, ZeroDivisionError):
        missing = _missing(MetricMissingReason.NUMERIC_INVALID)
        return missing, missing


def _acceleration_metric(
    *,
    target_index: int,
    benchmark_dates: Sequence[date],
    sector_values: Mapping[date, Decimal],
    benchmark_values: Mapping[date, Decimal],
) -> MetricValue:
    if target_index < 10:
        return _missing(MetricMissingReason.INSUFFICIENT_HISTORY)
    dates = (
        benchmark_dates[target_index - 10],
        benchmark_dates[target_index - 5],
        benchmark_dates[target_index],
    )
    if any(day not in sector_values for day in dates):
        return _missing(MetricMissingReason.SECTOR_DATE_MISSING)
    try:
        return MetricValue(
            value=relative_acceleration_5d(
                *(sector_values[day] for day in dates),
                *(benchmark_values[day] for day in dates),
            )
        )
    except (DecimalException, OverflowError, ValueError, ZeroDivisionError):
        return _missing(MetricMissingReason.NUMERIC_INVALID)


def _window_metric(
    *,
    target_index: int,
    benchmark_dates: Sequence[date],
    sector_values: Mapping[date, Decimal],
    calculator: Callable[[Sequence[Decimal]], Decimal],
) -> MetricValue:
    if target_index < 20:
        return _missing(MetricMissingReason.INSUFFICIENT_HISTORY)
    dates = benchmark_dates[target_index - 20 : target_index + 1]
    if any(day not in sector_values for day in dates):
        return _missing(MetricMissingReason.SECTOR_DATE_MISSING)
    try:
        return MetricValue(value=calculator(tuple(sector_values[day] for day in dates)))
    except (
        DecimalException,
        OverflowError,
        ValueError,
        ZeroDivisionError,
        statistics.StatisticsError,
    ):
        return _missing(MetricMissingReason.NUMERIC_INVALID)


def _compute_public_ranks(
    available: Mapping[SectorTicker, ValueSeries],
    benchmark: ValueSeries | None,
    metrics: Mapping[SectorTicker, PublicSectorMetrics],
    *,
    coverage_status: SectorCoverageStatus,
    target_date: date | None,
) -> dict[SectorTicker, RelativeRank]:
    if (
        benchmark is None
        or target_date is None
        or coverage_status not in {SectorCoverageStatus.PARTIAL, SectorCoverageStatus.NORMAL}
    ):
        reason = (
            "warming_up"
            if coverage_status is SectorCoverageStatus.WARMING_UP
            else "coverage_insufficient"
        )
        return _missing_ranks(reason, comparable_count=0)
    raw = {
        ticker: _raw_rank_values(series, benchmark, metrics[ticker], target_date=target_date)
        for ticker, series in available.items()
    }
    percentile_by_horizon: dict[RankHorizon, dict[SectorTicker, Decimal]] = {}
    for horizon in RANK_HORIZONS:
        values = {
            ticker: horizons[horizon] for ticker, horizons in raw.items() if horizon in horizons
        }
        if len(values) >= 8:
            percentile_by_horizon[horizon] = descending_midrank_percentiles(
                values,
                identity_order=SECTOR_TICKERS,
            )

    candidates: dict[SectorTicker, tuple[Decimal, tuple[RankHorizon, ...]]] = {}
    for ticker in SECTOR_TICKERS:
        used = tuple(
            horizon for horizon in RANK_HORIZONS if ticker in percentile_by_horizon.get(horizon, {})
        )
        if len(used) < 2:
            continue
        weight_total = sum((_RANK_WEIGHTS[horizon] for horizon in used), Decimal(0))
        with localcontext() as context:
            context.prec = 34
            context.rounding = ROUND_HALF_EVEN
            score = (
                sum(
                    (
                        percentile_by_horizon[horizon][ticker] * _RANK_WEIGHTS[horizon]
                        for horizon in used
                    ),
                    Decimal(0),
                )
                / weight_total
            )
        candidates[ticker] = (score, used)

    comparable_count = len(candidates)
    if comparable_count < 8:
        return _missing_ranks("insufficient_comparables", comparable_count=comparable_count)
    ordered = [ticker for ticker in SECTOR_TICKERS if ticker in candidates]
    ordered.sort(key=lambda ticker: candidates[ticker][0], reverse=True)
    ordinals = {ticker: ordinal for ordinal, ticker in enumerate(ordered, start=1)}
    return {
        ticker: (
            RelativeRank(
                score=candidates[ticker][0],
                ordinal=ordinals[ticker],
                comparable_sector_count=comparable_count,
                used_horizons=candidates[ticker][1],
            )
            if ticker in candidates
            else RelativeRank(
                comparable_sector_count=comparable_count,
                missing_reason=_rank_missing_reason(ticker, available, metrics),
            )
        )
        for ticker in SECTOR_TICKERS
    }


def _raw_rank_values(
    sector: ValueSeries,
    benchmark: ValueSeries,
    metrics: PublicSectorMetrics,
    *,
    target_date: date,
) -> dict[RankHorizon, Decimal]:
    benchmark_dates = tuple(point.trading_date for point in benchmark.points)
    try:
        target_index = benchmark_dates.index(target_date)
    except ValueError:
        return {}
    sector_values = {point.trading_date: point.value for point in sector.points}
    benchmark_values = {point.trading_date: point.value for point in benchmark.points}
    values: dict[RankHorizon, Decimal] = {}
    for horizon in RANK_HORIZONS:
        metric = getattr(metrics, f"iex_price_excess_{horizon}d")
        if metric.value is None or target_index < horizon:
            continue
        start, end = benchmark_dates[target_index - horizon], benchmark_dates[target_index]
        if start not in sector_values or end not in sector_values:
            continue
        values[horizon] = excess_return(
            sector_values[start],
            sector_values[end],
            benchmark_values[start],
            benchmark_values[end],
        )
    return values


def _compute_public_regime(
    *,
    ticker: SectorTicker,
    sector: ValueSeries | None,
    benchmark: ValueSeries | None,
    metrics: PublicSectorMetrics,
    coverage_status: SectorCoverageStatus,
    target_date: date | None,
) -> RegimeResult:
    missing_reason: MetricMissingReason | None
    if coverage_status is SectorCoverageStatus.INSUFFICIENT or benchmark is None:
        missing_reason = MetricMissingReason.COVERAGE_INSUFFICIENT
        observations: tuple[tuple[Decimal, Decimal], ...] = ()
    elif sector is None:
        missing_reason = _first_metric_missing_reason(metrics)
        observations = ()
    elif coverage_status is SectorCoverageStatus.WARMING_UP:
        missing_reason = MetricMissingReason.WARMING_UP
        observations = ()
    else:
        missing_reason = (
            metrics.iex_price_excess_21d.missing_reason
            or metrics.iex_price_relative_acceleration_5d.missing_reason
        )
        observations = (
            _regime_observations(sector, benchmark, target_date=target_date)
            if target_date is not None and missing_reason is None
            else ()
        )
    return classify_regime_history(
        ticker,
        observations,
        policy=PRIMARY_REGIME_POLICY,
        current_missing_reason=missing_reason,
    )


def _regime_observations(
    sector: ValueSeries,
    benchmark: ValueSeries,
    *,
    target_date: date,
) -> tuple[tuple[Decimal, Decimal], ...]:
    benchmark_dates = tuple(point.trading_date for point in benchmark.points)
    try:
        target_index = benchmark_dates.index(target_date)
    except ValueError:
        return ()
    sector_values = {point.trading_date: point.value for point in sector.points}
    benchmark_values = {point.trading_date: point.value for point in benchmark.points}
    observations: list[tuple[Decimal, Decimal]] = []
    for index in range(21, target_index + 1):
        strength_dates = benchmark_dates[index - 21 : index + 1]
        acceleration_dates = (
            benchmark_dates[index - 10],
            benchmark_dates[index - 5],
            benchmark_dates[index],
        )
        if any(day not in sector_values for day in (*strength_dates, *acceleration_dates)):
            continue
        try:
            strength = excess_return(
                sector_values[strength_dates[0]],
                sector_values[strength_dates[-1]],
                benchmark_values[strength_dates[0]],
                benchmark_values[strength_dates[-1]],
            )
            acceleration = relative_acceleration_5d(
                *(sector_values[day] for day in acceleration_dates),
                *(benchmark_values[day] for day in acceleration_dates),
            )
        except (DecimalException, OverflowError, ValueError, ZeroDivisionError):
            continue
        observations.append((strength, acceleration))
    return tuple(observations)


def _availability(
    ticker: SectorTicker,
    series: ValueSeries | None,
    failure: PublicSourceFailure | None,
) -> tuple[SectorAvailability, tuple[PublicDiagnosticCode, ...]]:
    if ticker is SectorTicker.XLRE:
        return SectorAvailability.PROVIDER_UNAVAILABLE, (PublicDiagnosticCode.PROVIDER_UNAVAILABLE,)
    if series is not None:
        return SectorAvailability.AVAILABLE, ()
    if failure is not None and failure.issue_code is PublicSourceIssueCode.INSUFFICIENT_HISTORY:
        return SectorAvailability.INSUFFICIENT_HISTORY, (PublicDiagnosticCode.INSUFFICIENT_HISTORY,)
    return SectorAvailability.TEMPORARILY_UNAVAILABLE, (
        PublicDiagnosticCode.TEMPORARILY_UNAVAILABLE,
    )


def _metric_reason_for_failure(
    failure: PublicSourceFailure | None,
) -> MetricMissingReason:
    if failure is not None and failure.issue_code is PublicSourceIssueCode.INSUFFICIENT_HISTORY:
        return MetricMissingReason.INSUFFICIENT_HISTORY
    if failure is not None and failure.issue_code is PublicSourceIssueCode.CALENDAR:
        return MetricMissingReason.SECTOR_DATE_MISSING
    return MetricMissingReason.COVERAGE_INSUFFICIENT


def _rank_missing_reason(
    ticker: SectorTicker,
    available: Mapping[SectorTicker, ValueSeries],
    metrics: Mapping[SectorTicker, PublicSectorMetrics],
) -> str:
    if ticker is SectorTicker.XLRE:
        return PublicDiagnosticCode.PROVIDER_UNAVAILABLE.value
    if ticker not in available:
        return _first_metric_missing_reason(metrics[ticker]).value
    return "insufficient_horizons"


def _first_metric_missing_reason(metrics: PublicSectorMetrics) -> MetricMissingReason:
    return (
        metrics.iex_price_return_1d.missing_reason
        or metrics.iex_price_return_5d.missing_reason
        or metrics.iex_price_return_21d.missing_reason
        or metrics.iex_price_return_63d.missing_reason
        or metrics.iex_price_excess_1d.missing_reason
        or metrics.iex_price_excess_5d.missing_reason
        or metrics.iex_price_excess_21d.missing_reason
        or metrics.iex_price_excess_63d.missing_reason
        or metrics.iex_price_relative_acceleration_5d.missing_reason
        or metrics.iex_price_realized_volatility_20d.missing_reason
        or metrics.iex_price_max_drawdown_20d.missing_reason
        or MetricMissingReason.COVERAGE_INSUFFICIENT
    )


def _missing_metrics(ticker: SectorTicker, reason: MetricMissingReason) -> PublicSectorMetrics:
    missing = _missing(reason)
    return PublicSectorMetrics(
        ticker=ticker,
        iex_price_return_1d=missing,
        iex_price_return_5d=missing,
        iex_price_return_21d=missing,
        iex_price_return_63d=missing,
        iex_price_excess_1d=missing,
        iex_price_excess_5d=missing,
        iex_price_excess_21d=missing,
        iex_price_excess_63d=missing,
        iex_price_relative_acceleration_5d=missing,
        iex_price_realized_volatility_20d=missing,
        iex_price_max_drawdown_20d=missing,
    )


def _missing_ranks(reason: str, *, comparable_count: int) -> dict[SectorTicker, RelativeRank]:
    return {
        ticker: RelativeRank(
            comparable_sector_count=comparable_count,
            missing_reason=reason,
        )
        for ticker in SECTOR_TICKERS
    }


def _missing(reason: MetricMissingReason) -> MetricValue:
    return MetricValue(missing_reason=reason)


__all__ = [
    "MetricHorizon",
    "build_public_series_bundle",
    "compute_public_sector_metrics",
    "compute_public_sector_snapshot",
    "resolve_public_freshness",
]
