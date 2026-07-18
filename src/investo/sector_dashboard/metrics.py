"""Pure NAV metric, relative-rank, and snapshot computation for u139."""

from __future__ import annotations

import math
import statistics
from collections.abc import Callable, Mapping, Sequence
from datetime import date
from decimal import (
    ROUND_HALF_EVEN,
    Decimal,
    DecimalException,
    localcontext,
)
from itertools import pairwise
from typing import Final, Literal

from investo.models.sector import (
    BENCHMARK_TICKER,
    RANK_HORIZONS,
    REGIME_BANDS_BPS,
    SECTOR_TICKERS,
    DiagnosticIssueCode,
    MetricMissingReason,
    MetricValue,
    NavSeries,
    PrivateDiagnostic,
    RankHorizon,
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
)
from investo.sector_dashboard.regime import (
    classify_regime_history,
    regime_policy_for_band,
)

MetricHorizon = Literal[1, 5, 21, 63]

_METRIC_HORIZONS: Final[tuple[MetricHorizon, ...]] = (1, 5, 21, 63)
_RANK_WEIGHTS: Final[dict[RankHorizon, Decimal]] = {
    5: Decimal("0.20"),
    21: Decimal("0.50"),
    63: Decimal("0.30"),
}
_TICKER_POSITION: Final[dict[SectorTicker, int]] = {
    ticker: position for position, ticker in enumerate(SECTOR_TICKERS)
}
_WARMING_ALLOWED_HORIZONS: Final[frozenset[int]] = frozenset({1, 5})


def nav_return(start_nav: Decimal, end_nav: Decimal) -> Decimal:
    """Return ``end_nav / start_nav - 1`` in the fixed decimal context."""

    _validate_navs((start_nav, end_nav))
    with localcontext() as context:
        context.prec = 34
        context.rounding = ROUND_HALF_EVEN
        result = end_nav / start_nav - Decimal(1)
    return _finite_decimal(result)


def nav_excess_return(
    sector_start_nav: Decimal,
    sector_end_nav: Decimal,
    benchmark_start_nav: Decimal,
    benchmark_end_nav: Decimal,
) -> Decimal:
    """Compute sector simple return minus SPY return on identical endpoints."""

    with localcontext() as context:
        context.prec = 34
        context.rounding = ROUND_HALF_EVEN
        result = nav_return(sector_start_nav, sector_end_nav) - nav_return(
            benchmark_start_nav,
            benchmark_end_nav,
        )
    return _finite_decimal(result)


def nav_relative_acceleration_5d(
    sector_t_minus_10: Decimal,
    sector_t_minus_5: Decimal,
    sector_t: Decimal,
    benchmark_t_minus_10: Decimal,
    benchmark_t_minus_5: Decimal,
    benchmark_t: Decimal,
) -> Decimal:
    """Subtract preceding 5D excess return from the current non-overlapping 5D excess."""

    current = nav_excess_return(
        sector_t_minus_5,
        sector_t,
        benchmark_t_minus_5,
        benchmark_t,
    )
    previous = nav_excess_return(
        sector_t_minus_10,
        sector_t_minus_5,
        benchmark_t_minus_10,
        benchmark_t_minus_5,
    )
    with localcontext() as context:
        context.prec = 34
        context.rounding = ROUND_HALF_EVEN
        result = current - previous
    return _finite_decimal(result)


def nav_realized_volatility_20d(navs: Sequence[Decimal]) -> Decimal:
    """Annualize the sample deviation of exactly twenty daily log NAV returns."""

    if len(navs) != 21:
        raise ValueError("20D realized volatility requires exactly 21 NAV points")
    _validate_navs(navs)
    daily_log_returns: list[float] = []
    with localcontext() as context:
        context.prec = 34
        context.rounding = ROUND_HALF_EVEN
        for previous, current in pairwise(navs):
            ratio = current / previous
            ratio_float = float(ratio)
            if not math.isfinite(ratio_float) or ratio_float <= 0:
                raise ValueError("daily NAV ratio must be finite and positive")
            daily_log_returns.append(math.log(ratio_float))
    volatility = statistics.stdev(daily_log_returns) * math.sqrt(252.0)
    if not math.isfinite(volatility) or volatility < 0:
        raise ValueError("realized volatility must be finite and non-negative")
    return Decimal(repr(volatility))


def nav_max_drawdown_20d(navs: Sequence[Decimal]) -> Decimal:
    """Return the minimum NAV/running-peak drawdown over exactly 21 points."""

    if len(navs) != 21:
        raise ValueError("20D max drawdown requires exactly 21 NAV points")
    _validate_navs(navs)
    peak = navs[0]
    worst = Decimal(0)
    with localcontext() as context:
        context.prec = 34
        context.rounding = ROUND_HALF_EVEN
        for nav in navs:
            peak = max(peak, nav)
            drawdown = nav / peak - Decimal(1)
            worst = min(worst, drawdown)
    return _finite_decimal(worst)


def descending_midrank_percentiles(
    values: Mapping[SectorTicker, Decimal],
) -> dict[SectorTicker, Decimal]:
    """Map values to descending tied midrank percentiles in ``[0, 1]``."""

    if len(values) < 2:
        raise ValueError("midrank percentiles require at least two values")
    if any(ticker not in _TICKER_POSITION for ticker in values):
        raise ValueError("midrank values must use sector tickers")
    if any(not value.is_finite() for value in values.values()):
        raise ValueError("midrank values must be finite")

    ordered = sorted(values.items(), key=lambda item: _TICKER_POSITION[item[0]])
    ordered.sort(key=lambda item: item[1], reverse=True)
    count = len(ordered)
    percentiles: dict[SectorTicker, Decimal] = {}
    position = 0
    with localcontext() as context:
        context.prec = 34
        context.rounding = ROUND_HALF_EVEN
        while position < count:
            group_end = position + 1
            while group_end < count and ordered[group_end][1] == ordered[position][1]:
                group_end += 1
            first_rank = Decimal(position + 1)
            last_rank = Decimal(group_end)
            midrank = (first_rank + last_rank) / Decimal(2)
            percentile = (Decimal(count) - midrank) / Decimal(count - 1)
            for group_position in range(position, group_end):
                percentiles[ordered[group_position][0]] = percentile
            position = group_end
    return percentiles


def compute_sector_metrics(
    sector: NavSeries,
    benchmark: NavSeries,
    *,
    coverage_status: SectorCoverageStatus,
    target_date: date | None = None,
) -> SectorMetrics:
    """Compute every metric slot for one sector on the SPY benchmark grid."""

    if sector.ticker is BENCHMARK_TICKER:
        raise ValueError("sector metrics cannot be computed for SPY")
    if benchmark.ticker is not BENCHMARK_TICKER:
        raise ValueError("benchmark series must be SPY")
    if coverage_status is SectorCoverageStatus.INSUFFICIENT:
        return _missing_sector_metrics(
            sector.ticker,
            MetricMissingReason.COVERAGE_INSUFFICIENT,
        )

    benchmark_dates = tuple(point.trading_date for point in benchmark.points)
    requested_date = target_date or benchmark.latest_date
    try:
        target_index = benchmark_dates.index(requested_date)
    except ValueError:
        return _missing_sector_metrics(
            sector.ticker,
            MetricMissingReason.BENCHMARK_DATE_MISSING,
        )

    sector_nav = {point.trading_date: point.nav for point in sector.points}
    benchmark_nav = {point.trading_date: point.nav for point in benchmark.points}
    returns: dict[MetricHorizon, MetricValue] = {}
    excess: dict[MetricHorizon, MetricValue] = {}
    for horizon in _METRIC_HORIZONS:
        if (
            coverage_status is SectorCoverageStatus.WARMING_UP
            and horizon not in _WARMING_ALLOWED_HORIZONS
        ):
            returns[horizon] = _missing(MetricMissingReason.WARMING_UP)
            excess[horizon] = _missing(MetricMissingReason.WARMING_UP)
            continue
        returns[horizon], excess[horizon] = _return_pair(
            horizon=horizon,
            target_index=target_index,
            benchmark_dates=benchmark_dates,
            sector_nav=sector_nav,
            benchmark_nav=benchmark_nav,
        )

    if coverage_status is SectorCoverageStatus.WARMING_UP:
        acceleration = _missing(MetricMissingReason.WARMING_UP)
        volatility = _missing(MetricMissingReason.WARMING_UP)
        drawdown = _missing(MetricMissingReason.WARMING_UP)
    else:
        acceleration = _acceleration_metric(
            target_index=target_index,
            benchmark_dates=benchmark_dates,
            sector_nav=sector_nav,
            benchmark_nav=benchmark_nav,
        )
        volatility = _window_metric(
            target_index=target_index,
            benchmark_dates=benchmark_dates,
            sector_nav=sector_nav,
            calculator=nav_realized_volatility_20d,
        )
        drawdown = _window_metric(
            target_index=target_index,
            benchmark_dates=benchmark_dates,
            sector_nav=sector_nav,
            calculator=nav_max_drawdown_20d,
        )

    return SectorMetrics(
        ticker=sector.ticker,
        nav_return_1d=returns[1],
        nav_return_5d=returns[5],
        nav_return_21d=returns[21],
        nav_return_63d=returns[63],
        nav_excess_1d=excess[1],
        nav_excess_5d=excess[5],
        nav_excess_21d=excess[21],
        nav_excess_63d=excess[63],
        nav_relative_acceleration_5d=acceleration,
        nav_realized_volatility_20d=volatility,
        nav_max_drawdown_20d=drawdown,
    )


def compute_relative_ranks(
    metrics_by_ticker: Mapping[SectorTicker, SectorMetrics],
    *,
    coverage_status: SectorCoverageStatus,
) -> dict[SectorTicker, RelativeRank]:
    """Compute deterministic ``relative_rank_v1`` results for all eleven sectors."""

    if set(metrics_by_ticker) != set(SECTOR_TICKERS):
        raise ValueError("rank input must contain exactly the eleven sector metrics")
    if any(metrics.ticker is not ticker for ticker, metrics in metrics_by_ticker.items()):
        raise ValueError("rank mapping keys must match metric tickers")
    if coverage_status is SectorCoverageStatus.INSUFFICIENT:
        return _missing_ranks("coverage_insufficient", comparable_count=0)
    if coverage_status is SectorCoverageStatus.WARMING_UP:
        return _missing_ranks("warming_up", comparable_count=0)

    excess_by_ticker = {
        ticker: {
            horizon: value
            for horizon in RANK_HORIZONS
            if (value := _excess_metric(metrics, horizon).value) is not None
        }
        for ticker, metrics in metrics_by_ticker.items()
    }
    return _compute_relative_ranks_from_values(excess_by_ticker)


def _compute_relative_ranks_from_values(
    excess_by_ticker: Mapping[SectorTicker, Mapping[RankHorizon, Decimal]],
) -> dict[SectorTicker, RelativeRank]:
    percentile_by_horizon: dict[RankHorizon, dict[SectorTicker, Decimal]] = {}
    for horizon in RANK_HORIZONS:
        available = {
            ticker: values[horizon]
            for ticker, values in excess_by_ticker.items()
            if horizon in values
        }
        if len(available) >= 8:
            percentile_by_horizon[horizon] = descending_midrank_percentiles(available)

    candidate_scores: dict[SectorTicker, tuple[Decimal, tuple[RankHorizon, ...]]] = {}
    for ticker in SECTOR_TICKERS:
        used_horizons = tuple(
            horizon for horizon in RANK_HORIZONS if ticker in percentile_by_horizon.get(horizon, {})
        )
        if len(used_horizons) < 2:
            continue
        weight_total = sum((_RANK_WEIGHTS[horizon] for horizon in used_horizons), Decimal(0))
        with localcontext() as context:
            context.prec = 34
            context.rounding = ROUND_HALF_EVEN
            score = (
                sum(
                    (
                        percentile_by_horizon[horizon][ticker] * _RANK_WEIGHTS[horizon]
                        for horizon in used_horizons
                    ),
                    Decimal(0),
                )
                / weight_total
            )
        candidate_scores[ticker] = (_finite_decimal(score), used_horizons)

    comparable_count = len(candidate_scores)
    if comparable_count < 8:
        return _missing_ranks(
            "insufficient_comparables",
            comparable_count=comparable_count,
        )

    ordered = [ticker for ticker in SECTOR_TICKERS if ticker in candidate_scores]
    ordered.sort(key=lambda ticker: candidate_scores[ticker][0], reverse=True)
    ordinal_by_ticker = {ticker: ordinal for ordinal, ticker in enumerate(ordered, start=1)}
    ranks: dict[SectorTicker, RelativeRank] = {}
    for ticker in SECTOR_TICKERS:
        candidate = candidate_scores.get(ticker)
        if candidate is None:
            ranks[ticker] = RelativeRank(
                comparable_sector_count=comparable_count,
                missing_reason="insufficient_horizons",
            )
            continue
        score, used_horizons = candidate
        ranks[ticker] = RelativeRank(
            score=score,
            ordinal=ordinal_by_ticker[ticker],
            comparable_sector_count=comparable_count,
            used_horizons=used_horizons,
        )
    return ranks


def compute_sector_snapshot(bundle: SectorSeriesBundle) -> SectorDashboardSnapshot:
    """Build the immutable metric/regime/rank snapshot from one canonical bundle."""

    benchmark = bundle.benchmark
    available_by_ticker = {series.ticker: series for series in bundle.sectors}
    metrics_by_ticker: dict[SectorTicker, SectorMetrics] = {}
    for ticker in SECTOR_TICKERS:
        sector = available_by_ticker.get(ticker)
        if (
            benchmark is None
            or sector is None
            or bundle.coverage.status is SectorCoverageStatus.INSUFFICIENT
        ):
            metrics_by_ticker[ticker] = _missing_sector_metrics(
                ticker,
                MetricMissingReason.COVERAGE_INSUFFICIENT,
            )
        else:
            metrics_by_ticker[ticker] = compute_sector_metrics(
                sector,
                benchmark,
                coverage_status=bundle.coverage.status,
                target_date=bundle.as_of_date,
            )

    if (
        benchmark is not None
        and bundle.as_of_date is not None
        and bundle.coverage.status in (SectorCoverageStatus.NORMAL, SectorCoverageStatus.PARTIAL)
    ):
        raw_rank_values = {
            ticker: _raw_rank_excess_values(
                sector,
                benchmark,
                target_date=bundle.as_of_date,
                metrics=metrics_by_ticker[ticker],
            )
            for ticker, sector in available_by_ticker.items()
        }
        raw_rank_values.update(
            {ticker: {} for ticker in SECTOR_TICKERS if ticker not in raw_rank_values}
        )
        ranks = _compute_relative_ranks_from_values(raw_rank_values)
    else:
        ranks = compute_relative_ranks(
            metrics_by_ticker,
            coverage_status=bundle.coverage.status,
        )
    records: list[SectorRecord] = []
    metric_diagnostics: list[PrivateDiagnostic] = []
    for ticker in SECTOR_TICKERS:
        metrics = metrics_by_ticker[ticker]
        sector = available_by_ticker.get(ticker)
        primary_regime, sensitivity = _compute_regimes(
            ticker=ticker,
            sector=sector,
            benchmark=benchmark,
            metrics=metrics,
            coverage_status=bundle.coverage.status,
            target_date=bundle.as_of_date,
        )
        diagnostics = _metric_history_diagnostics(metrics)
        metric_diagnostics.extend(diagnostics)
        records.append(
            SectorRecord(
                ticker=ticker,
                metrics=metrics,
                primary_regime=primary_regime,
                sensitivity_regimes=sensitivity,
                relative_rank=ranks[ticker],
                diagnostic_codes=tuple(diagnostic.issue_code for diagnostic in diagnostics),
            )
        )

    return SectorDashboardSnapshot(
        as_of_date=bundle.as_of_date,
        coverage=bundle.coverage,
        records=tuple(records),
        diagnostics=(*bundle.diagnostics, *metric_diagnostics),
        input_fingerprint=bundle.input_fingerprint,
    )


def _return_pair(
    *,
    horizon: MetricHorizon,
    target_index: int,
    benchmark_dates: Sequence[date],
    sector_nav: Mapping[date, Decimal],
    benchmark_nav: Mapping[date, Decimal],
) -> tuple[MetricValue, MetricValue]:
    if target_index < horizon:
        missing = _missing(MetricMissingReason.INSUFFICIENT_HISTORY)
        return missing, missing
    required_dates = benchmark_dates[target_index - horizon : target_index + 1]
    if any(required_date not in sector_nav for required_date in required_dates):
        missing = _missing(MetricMissingReason.SECTOR_DATE_MISSING)
        return missing, missing
    start_date = required_dates[0]
    end_date = required_dates[-1]
    try:
        sector_return = nav_return(sector_nav[start_date], sector_nav[end_date])
        excess_return = nav_excess_return(
            sector_nav[start_date],
            sector_nav[end_date],
            benchmark_nav[start_date],
            benchmark_nav[end_date],
        )
        return MetricValue(value=sector_return), MetricValue(value=excess_return)
    except (DecimalException, OverflowError, ValueError, ZeroDivisionError):
        missing = _missing(MetricMissingReason.NUMERIC_INVALID)
        return missing, missing


def _acceleration_metric(
    *,
    target_index: int,
    benchmark_dates: Sequence[date],
    sector_nav: Mapping[date, Decimal],
    benchmark_nav: Mapping[date, Decimal],
) -> MetricValue:
    if target_index < 10:
        return _missing(MetricMissingReason.INSUFFICIENT_HISTORY)
    required_dates = (
        benchmark_dates[target_index - 10],
        benchmark_dates[target_index - 5],
        benchmark_dates[target_index],
    )
    if any(required_date not in sector_nav for required_date in required_dates):
        return _missing(MetricMissingReason.SECTOR_DATE_MISSING)
    try:
        result = nav_relative_acceleration_5d(
            *(sector_nav[required_date] for required_date in required_dates),
            *(benchmark_nav[required_date] for required_date in required_dates),
        )
        return MetricValue(value=result)
    except (DecimalException, OverflowError, ValueError, ZeroDivisionError):
        return _missing(MetricMissingReason.NUMERIC_INVALID)


def _window_metric(
    *,
    target_index: int,
    benchmark_dates: Sequence[date],
    sector_nav: Mapping[date, Decimal],
    calculator: Callable[[Sequence[Decimal]], Decimal],
) -> MetricValue:
    if target_index < 20:
        return _missing(MetricMissingReason.INSUFFICIENT_HISTORY)
    dates = benchmark_dates[target_index - 20 : target_index + 1]
    if any(required_date not in sector_nav for required_date in dates):
        return _missing(MetricMissingReason.SECTOR_DATE_MISSING)
    navs = tuple(sector_nav[required_date] for required_date in dates)
    try:
        result = calculator(navs)
        return MetricValue(value=result)
    except (
        DecimalException,
        OverflowError,
        ValueError,
        ZeroDivisionError,
        statistics.StatisticsError,
    ):
        return _missing(MetricMissingReason.NUMERIC_INVALID)


def _regime_observations(
    sector: NavSeries,
    benchmark: NavSeries,
    *,
    target_date: date,
) -> tuple[tuple[Decimal, Decimal], ...]:
    benchmark_dates = tuple(point.trading_date for point in benchmark.points)
    try:
        target_index = benchmark_dates.index(target_date)
    except ValueError:
        return ()
    sector_nav = {point.trading_date: point.nav for point in sector.points}
    benchmark_nav = {point.trading_date: point.nav for point in benchmark.points}
    observations: list[tuple[Decimal, Decimal]] = []
    for index in range(21, target_index + 1):
        strength_dates = benchmark_dates[index - 21 : index + 1]
        acceleration_dates = (
            benchmark_dates[index - 10],
            benchmark_dates[index - 5],
            benchmark_dates[index],
        )
        required_dates = (*strength_dates, *acceleration_dates)
        if any(required_date not in sector_nav for required_date in required_dates):
            continue
        try:
            strength = nav_excess_return(
                sector_nav[strength_dates[0]],
                sector_nav[strength_dates[-1]],
                benchmark_nav[strength_dates[0]],
                benchmark_nav[strength_dates[-1]],
            )
            acceleration = nav_relative_acceleration_5d(
                *(sector_nav[required_date] for required_date in acceleration_dates),
                *(benchmark_nav[required_date] for required_date in acceleration_dates),
            )
        except (DecimalException, OverflowError, ValueError, ZeroDivisionError):
            continue
        observations.append((strength, acceleration))
    return tuple(observations)


def _raw_rank_excess_values(
    sector: NavSeries,
    benchmark: NavSeries,
    *,
    target_date: date,
    metrics: SectorMetrics,
) -> dict[RankHorizon, Decimal]:
    benchmark_dates = tuple(point.trading_date for point in benchmark.points)
    try:
        target_index = benchmark_dates.index(target_date)
    except ValueError:
        return {}
    sector_nav = {point.trading_date: point.nav for point in sector.points}
    benchmark_nav = {point.trading_date: point.nav for point in benchmark.points}
    values: dict[RankHorizon, Decimal] = {}
    for horizon in RANK_HORIZONS:
        if _excess_metric(metrics, horizon).value is None or target_index < horizon:
            continue
        start_date = benchmark_dates[target_index - horizon]
        end_date = benchmark_dates[target_index]
        if start_date not in sector_nav or end_date not in sector_nav:
            continue
        try:
            values[horizon] = nav_excess_return(
                sector_nav[start_date],
                sector_nav[end_date],
                benchmark_nav[start_date],
                benchmark_nav[end_date],
            )
        except (DecimalException, OverflowError, ValueError, ZeroDivisionError):
            continue
    return values


def _compute_regimes(
    *,
    ticker: SectorTicker,
    sector: NavSeries | None,
    benchmark: NavSeries | None,
    metrics: SectorMetrics,
    coverage_status: SectorCoverageStatus,
    target_date: date | None,
) -> tuple[RegimeResult, dict[int, SectorRegime]]:
    missing_reason: MetricMissingReason | None
    if coverage_status is SectorCoverageStatus.INSUFFICIENT or sector is None or benchmark is None:
        missing_reason = MetricMissingReason.COVERAGE_INSUFFICIENT
        observations: tuple[tuple[Decimal, Decimal], ...] = ()
    elif coverage_status is SectorCoverageStatus.WARMING_UP:
        missing_reason = MetricMissingReason.WARMING_UP
        observations = ()
    else:
        strength = metrics.nav_excess_21d
        acceleration = metrics.nav_relative_acceleration_5d
        missing_reason = strength.missing_reason or acceleration.missing_reason
        observations = (
            _regime_observations(sector, benchmark, target_date=target_date)
            if target_date is not None and missing_reason is None
            else ()
        )

    results = {
        band: classify_regime_history(
            ticker,
            observations,
            policy=regime_policy_for_band(band),
            current_missing_reason=missing_reason,
        )
        for band in REGIME_BANDS_BPS
    }
    return results[10], {band: result.regime for band, result in results.items()}


def _metric_history_diagnostics(metrics: SectorMetrics) -> tuple[PrivateDiagnostic, ...]:
    diagnostics: list[PrivateDiagnostic] = []
    for metric_name in SectorMetricName:
        metric = getattr(metrics, metric_name.value)
        if metric.missing_reason is MetricMissingReason.INSUFFICIENT_HISTORY:
            diagnostics.append(
                PrivateDiagnostic(
                    issue_code=DiagnosticIssueCode.METRIC_INSUFFICIENT_HISTORY,
                    ticker=metrics.ticker,
                    metric_name=metric_name,
                )
            )
    return tuple(diagnostics)


def _missing_sector_metrics(
    ticker: SectorTicker,
    reason: MetricMissingReason,
) -> SectorMetrics:
    missing = _missing(reason)
    return SectorMetrics(
        ticker=ticker,
        nav_return_1d=missing,
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


def _missing_ranks(reason: str, *, comparable_count: int) -> dict[SectorTicker, RelativeRank]:
    return {
        ticker: RelativeRank(
            comparable_sector_count=comparable_count,
            missing_reason=reason,
        )
        for ticker in SECTOR_TICKERS
    }


def _excess_metric(metrics: SectorMetrics, horizon: RankHorizon) -> MetricValue:
    if horizon == 5:
        return metrics.nav_excess_5d
    if horizon == 21:
        return metrics.nav_excess_21d
    return metrics.nav_excess_63d


def _missing(reason: MetricMissingReason) -> MetricValue:
    return MetricValue(missing_reason=reason)


def _validate_navs(navs: Sequence[Decimal]) -> None:
    if any(not nav.is_finite() or nav <= 0 for nav in navs):
        raise ValueError("NAV values must be finite and strictly positive")


def _finite_decimal(value: Decimal) -> Decimal:
    if not value.is_finite():
        raise ValueError("numeric result must be finite")
    return value


__all__ = [
    "MetricHorizon",
    "compute_relative_ranks",
    "compute_sector_metrics",
    "compute_sector_snapshot",
    "descending_midrank_percentiles",
    "nav_excess_return",
    "nav_max_drawdown_20d",
    "nav_realized_volatility_20d",
    "nav_relative_acceleration_5d",
    "nav_return",
]
