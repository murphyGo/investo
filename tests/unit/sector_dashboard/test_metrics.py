from __future__ import annotations

from datetime import date, timedelta
from decimal import ROUND_HALF_EVEN, Decimal, localcontext

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from investo.models.sector import (
    BENCHMARK_TICKER,
    SECTOR_TICKERS,
    AxisState,
    CoverageSummary,
    MetricMissingReason,
    MetricValue,
    NavPoint,
    NavSeries,
    SectorCoverageStatus,
    SectorMetrics,
    SectorRegime,
    SectorSeriesBundle,
    SectorTicker,
)
from investo.sector_dashboard.metrics import (
    compute_relative_ranks,
    compute_sector_metrics,
    compute_sector_snapshot,
    descending_midrank_percentiles,
    nav_excess_return,
    nav_max_drawdown_20d,
    nav_realized_volatility_20d,
    nav_relative_acceleration_5d,
    nav_return,
)

_PBT_SETTINGS = settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=(HealthCheck.too_slow,),
)
_START_DATE = date(2026, 1, 1)


def _series(
    ticker: SectorTicker,
    navs: list[Decimal],
    *,
    missing_indexes: frozenset[int] = frozenset(),
) -> NavSeries:
    points = tuple(
        NavPoint(trading_date=_START_DATE + timedelta(days=index), nav=nav)
        for index, nav in enumerate(navs)
        if index not in missing_indexes
    )
    return NavSeries(
        ticker=ticker,
        points=points,
        first_date=points[0].trading_date,
        latest_date=points[-1].trading_date,
    )


def _coverage(
    status: SectorCoverageStatus,
    *,
    count: int,
    missing_tickers: tuple[SectorTicker, ...] = (),
) -> CoverageSummary:
    return CoverageSummary(
        status=status,
        available_sector_count=11 - len(missing_tickers),
        benchmark_available=True,
        common_as_of=_START_DATE + timedelta(days=count - 1),
        benchmark_observation_count=count,
        missing_tickers=missing_tickers,
    )


def _bundle(
    *,
    count: int = 70,
    status: SectorCoverageStatus = SectorCoverageStatus.NORMAL,
    missing_tickers: tuple[SectorTicker, ...] = (),
    sector_overrides: dict[SectorTicker, NavSeries] | None = None,
) -> SectorSeriesBundle:
    navs = [Decimal("100") for _ in range(count)]
    benchmark = _series(BENCHMARK_TICKER, navs)
    overrides = sector_overrides or {}
    sectors = tuple(
        overrides.get(ticker, _series(ticker, navs))
        for ticker in SECTOR_TICKERS
        if ticker not in missing_tickers
    )
    coverage = _coverage(
        status,
        count=count,
        missing_tickers=missing_tickers,
    )
    return SectorSeriesBundle(
        as_of_date=benchmark.latest_date,
        benchmark=benchmark,
        sectors=sectors,
        coverage=coverage,
        input_fingerprint="sha256:" + "a" * 64,
    )


def _metrics_with_excess(
    ticker: SectorTicker,
    *,
    value_5d: Decimal,
    value_21d: Decimal,
    value_63d: Decimal,
) -> SectorMetrics:
    zero = MetricValue(value=Decimal(0))
    return SectorMetrics(
        ticker=ticker,
        nav_return_1d=zero,
        nav_return_5d=zero,
        nav_return_21d=zero,
        nav_return_63d=zero,
        nav_excess_1d=zero,
        nav_excess_5d=MetricValue(value=value_5d),
        nav_excess_21d=MetricValue(value=value_21d),
        nav_excess_63d=MetricValue(value=value_63d),
        nav_relative_acceleration_5d=zero,
        nav_realized_volatility_20d=zero,
        nav_max_drawdown_20d=zero,
    )


def test_fixed_metric_formulas_use_adjacent_non_overlapping_windows() -> None:
    assert nav_return(Decimal("100"), Decimal("110")) == Decimal("0.1")
    assert nav_excess_return(
        Decimal("100"),
        Decimal("110"),
        Decimal("100"),
        Decimal("105"),
    ) == Decimal("0.05")
    with localcontext() as context:
        context.prec = 34
        context.rounding = ROUND_HALF_EVEN
        expected_acceleration = nav_excess_return(
            Decimal("102"),
            Decimal("108"),
            Decimal("101"),
            Decimal("104"),
        ) - nav_excess_return(
            Decimal("100"),
            Decimal("102"),
            Decimal("100"),
            Decimal("101"),
        )
    assert (
        nav_relative_acceleration_5d(
            Decimal("100"),
            Decimal("102"),
            Decimal("108"),
            Decimal("100"),
            Decimal("101"),
            Decimal("104"),
        )
        == expected_acceleration
    )


def test_realized_volatility_float_boundary_has_fixed_golden_vector() -> None:
    navs = [
        Decimal(str(value))
        for value in (
            100,
            101,
            99,
            102,
            103,
            101,
            104,
            106,
            105,
            107,
            108,
            106,
            109,
            111,
            110,
            112,
            115,
            114,
            116,
            118,
            117,
        )
    ]
    assert nav_realized_volatility_20d(navs) == Decimal("0.27488142165029567")


def test_midrank_ties_share_numeric_percentile_without_changing_display_key() -> None:
    values = {
        SectorTicker.XLC: Decimal("3"),
        SectorTicker.XLY: Decimal("3"),
        SectorTicker.XLP: Decimal("2"),
        SectorTicker.XLE: Decimal("1"),
    }

    percentiles = descending_midrank_percentiles(values)

    assert percentiles[SectorTicker.XLC] == percentiles[SectorTicker.XLY]
    assert percentiles[SectorTicker.XLC] == Decimal("0.8333333333333333333333333333333333")
    assert percentiles[SectorTicker.XLP] == Decimal("0.3333333333333333333333333333333333")
    assert percentiles[SectorTicker.XLE] == Decimal(0)


def test_rank_renormalizes_weights_when_one_window_is_unavailable() -> None:
    missing = MetricValue(missing_reason=MetricMissingReason.INSUFFICIENT_HISTORY)
    metrics = {
        ticker: _metrics_with_excess(
            ticker,
            value_5d=Decimal(index),
            value_21d=Decimal(index),
            value_63d=Decimal(index),
        ).model_copy(update={"nav_excess_63d": missing})
        for index, ticker in enumerate(SECTOR_TICKERS)
    }

    ranks = compute_relative_ranks(metrics, coverage_status=SectorCoverageStatus.NORMAL)

    assert all(rank.used_horizons == (5, 21) for rank in ranks.values())
    assert ranks[SectorTicker.XLU].score == Decimal("1.0000000000")
    assert ranks[SectorTicker.XLC].score == Decimal("0.0000000000")


def test_equal_series_produces_zero_relative_metrics_lagging_regime_and_tied_rank() -> None:
    snapshot = compute_sector_snapshot(_bundle())

    assert snapshot.model_dump_json() == compute_sector_snapshot(_bundle()).model_dump_json()
    for ordinal, record in enumerate(snapshot.records, start=1):
        assert record.metrics.nav_excess_21d.value == Decimal("0.0000000000")
        assert record.metrics.nav_relative_acceleration_5d.value == Decimal("0.0000000000")
        assert record.metrics.nav_realized_volatility_20d.value == Decimal("0.0000000000")
        assert record.metrics.nav_max_drawdown_20d.value == Decimal("0.0000000000")
        assert record.primary_regime.regime is SectorRegime.LAGGING
        assert record.primary_regime.strength_state is AxisState.NEGATIVE
        assert record.primary_regime.acceleration_state is AxisState.NEGATIVE
        assert set(record.sensitivity_regimes.values()) == {SectorRegime.LAGGING}
        assert record.relative_rank.score == Decimal("0.5000000000")
        assert record.relative_rank.ordinal == ordinal


def test_snapshot_rank_uses_raw_excess_values_before_snapshot_quantization() -> None:
    sector_overrides: dict[SectorTicker, NavSeries] = {}
    for index, ticker in enumerate(SECTOR_TICKERS):
        navs = [Decimal("100") for _ in range(70)]
        navs[-1] += Decimal(index) * Decimal("0.0000000001")
        sector_overrides[ticker] = _series(ticker, navs)

    snapshot = compute_sector_snapshot(_bundle(sector_overrides=sector_overrides))
    by_ticker = {record.ticker: record for record in snapshot.records}

    assert all(
        record.metrics.nav_excess_63d.value == Decimal("0.0000000000")
        for record in snapshot.records
    )
    assert by_ticker[SectorTicker.XLU].relative_rank.ordinal == 1
    assert by_ticker[SectorTicker.XLC].relative_rank.ordinal == 11
    assert (
        by_ticker[SectorTicker.XLU].relative_rank.score
        > by_ticker[SectorTicker.XLC].relative_rank.score
    )


def test_snapshot_regime_replays_history_and_sensitivity_at_closed_boundaries() -> None:
    navs = [Decimal("100") for _ in range(70)]
    navs[68] = Decimal("101")
    navs[69] = Decimal("99.95")
    snapshot = compute_sector_snapshot(
        _bundle(
            sector_overrides={
                SectorTicker.XLC: _series(SectorTicker.XLC, navs),
            }
        )
    )
    xlc = next(record for record in snapshot.records if record.ticker is SectorTicker.XLC)

    assert xlc.metrics.nav_excess_21d.value == Decimal("-0.0005000000")
    assert xlc.metrics.nav_relative_acceleration_5d.value == Decimal("-0.0005000000")
    assert xlc.primary_regime.regime is SectorRegime.LEADING
    assert xlc.sensitivity_regimes[0] is SectorRegime.LAGGING
    assert xlc.sensitivity_regimes[5] is SectorRegime.LEADING
    assert xlc.sensitivity_regimes[10] is SectorRegime.LEADING


def test_historical_strength_with_interior_gap_cannot_change_hysteresis_state() -> None:
    navs = [Decimal("100") for _ in range(70)]
    navs[50] = Decimal("101")
    sector = _series(
        SectorTicker.XLC,
        navs,
        missing_indexes=frozenset({30}),
    )
    snapshot = compute_sector_snapshot(_bundle(sector_overrides={SectorTicker.XLC: sector}))
    xlc = next(record for record in snapshot.records if record.ticker is SectorTicker.XLC)

    assert xlc.metrics.nav_excess_21d.value == Decimal("0.0000000000")
    assert xlc.metrics.nav_relative_acceleration_5d.value == Decimal("0.0000000000")
    assert xlc.primary_regime.strength_state is AxisState.NEGATIVE
    assert xlc.primary_regime.regime is SectorRegime.RECOVERING


def test_sparse_endpoint_and_interior_discontinuity_are_never_interpolated() -> None:
    navs = [Decimal("100") for _ in range(70)]
    endpoint_gap = _series(SectorTicker.XLC, navs, missing_indexes=frozenset({64}))
    interior_gap = _series(SectorTicker.XLY, navs, missing_indexes=frozenset({55}))
    five_day_interior_gap = _series(
        SectorTicker.XLP,
        navs,
        missing_indexes=frozenset({66}),
    )
    snapshot = compute_sector_snapshot(
        _bundle(
            sector_overrides={
                SectorTicker.XLC: endpoint_gap,
                SectorTicker.XLY: interior_gap,
                SectorTicker.XLP: five_day_interior_gap,
            }
        )
    )
    by_ticker = {record.ticker: record for record in snapshot.records}

    xlc = by_ticker[SectorTicker.XLC].metrics
    assert xlc.nav_return_5d.missing_reason is MetricMissingReason.SECTOR_DATE_MISSING
    assert xlc.nav_excess_5d.missing_reason is MetricMissingReason.SECTOR_DATE_MISSING
    assert (
        xlc.nav_relative_acceleration_5d.missing_reason is MetricMissingReason.SECTOR_DATE_MISSING
    )

    xly = by_ticker[SectorTicker.XLY].metrics
    assert xly.nav_return_21d.missing_reason is MetricMissingReason.SECTOR_DATE_MISSING
    assert xly.nav_excess_21d.missing_reason is MetricMissingReason.SECTOR_DATE_MISSING
    assert xly.nav_realized_volatility_20d.missing_reason is MetricMissingReason.SECTOR_DATE_MISSING
    assert xly.nav_max_drawdown_20d.missing_reason is MetricMissingReason.SECTOR_DATE_MISSING

    xlp = by_ticker[SectorTicker.XLP].metrics
    assert xlp.nav_return_5d.missing_reason is MetricMissingReason.SECTOR_DATE_MISSING
    assert xlp.nav_excess_5d.missing_reason is MetricMissingReason.SECTOR_DATE_MISSING
    assert xlp.nav_relative_acceleration_5d.value == Decimal("0.0000000000")


def test_warming_up_exposes_only_1d_5d_and_suppresses_rank_and_regime() -> None:
    snapshot = compute_sector_snapshot(_bundle(count=10, status=SectorCoverageStatus.WARMING_UP))

    for record in snapshot.records:
        assert record.metrics.nav_return_1d.value == Decimal("0.0000000000")
        assert record.metrics.nav_excess_5d.value == Decimal("0.0000000000")
        assert record.metrics.nav_return_21d.missing_reason is MetricMissingReason.WARMING_UP
        assert (
            record.metrics.nav_relative_acceleration_5d.missing_reason
            is MetricMissingReason.WARMING_UP
        )
        assert record.primary_regime.regime is SectorRegime.INSUFFICIENT
        assert record.primary_regime.missing_reason is MetricMissingReason.WARMING_UP
        assert record.relative_rank.score is None
        assert record.relative_rank.missing_reason == "warming_up"


def test_insufficient_coverage_suppresses_every_sector_claim() -> None:
    missing = tuple(SECTOR_TICKERS[7:])
    snapshot = compute_sector_snapshot(
        _bundle(
            status=SectorCoverageStatus.INSUFFICIENT,
            missing_tickers=missing,
        )
    )

    for record in snapshot.records:
        assert (
            record.metrics.nav_return_1d.missing_reason is MetricMissingReason.COVERAGE_INSUFFICIENT
        )
        assert record.primary_regime.regime is SectorRegime.INSUFFICIENT
        assert record.relative_rank.score is None


def test_metric_missing_reasons_cover_benchmark_history_sector_and_numeric_failures() -> None:
    navs = [Decimal("100") for _ in range(70)]
    benchmark = _series(BENCHMARK_TICKER, navs)
    sector = _series(SectorTicker.XLC, navs)

    benchmark_missing = compute_sector_metrics(
        sector,
        benchmark,
        coverage_status=SectorCoverageStatus.NORMAL,
        target_date=date(2030, 1, 1),
    )
    assert (
        benchmark_missing.nav_return_1d.missing_reason is MetricMissingReason.BENCHMARK_DATE_MISSING
    )

    short = compute_sector_metrics(
        _series(SectorTicker.XLC, navs[:6]),
        _series(BENCHMARK_TICKER, navs[:6]),
        coverage_status=SectorCoverageStatus.NORMAL,
    )
    assert short.nav_return_21d.missing_reason is MetricMissingReason.INSUFFICIENT_HISTORY

    huge_navs = [Decimal("1E-999999") for _ in range(70)]
    huge_navs[-1] = Decimal("1E+999999")
    numeric = compute_sector_metrics(
        _series(SectorTicker.XLC, huge_navs),
        benchmark,
        coverage_status=SectorCoverageStatus.NORMAL,
    )
    assert numeric.nav_return_1d.missing_reason is MetricMissingReason.NUMERIC_INVALID


@_PBT_SETTINGS
@given(
    sector_start=st.decimals(min_value="0.01", max_value="100000", places=6),
    sector_end=st.decimals(min_value="0.01", max_value="100000", places=6),
    benchmark_start=st.decimals(min_value="0.01", max_value="100000", places=6),
    benchmark_end=st.decimals(min_value="0.01", max_value="100000", places=6),
)
def test_return_and_excess_identity_property(
    sector_start: Decimal,
    sector_end: Decimal,
    benchmark_start: Decimal,
    benchmark_end: Decimal,
) -> None:
    with localcontext() as context:
        context.prec = 34
        context.rounding = ROUND_HALF_EVEN
        expected = nav_return(sector_start, sector_end) - nav_return(
            benchmark_start,
            benchmark_end,
        )
    assert (
        nav_excess_return(
            sector_start,
            sector_end,
            benchmark_start,
            benchmark_end,
        )
        == expected
    )


@_PBT_SETTINGS
@given(
    sector_t_minus_10=st.decimals(min_value="0.01", max_value="100000", places=6),
    sector_t_minus_5=st.decimals(min_value="0.01", max_value="100000", places=6),
    sector_t=st.decimals(min_value="0.01", max_value="100000", places=6),
    benchmark_t_minus_10=st.decimals(min_value="0.01", max_value="100000", places=6),
    benchmark_t_minus_5=st.decimals(min_value="0.01", max_value="100000", places=6),
    benchmark_t=st.decimals(min_value="0.01", max_value="100000", places=6),
)
def test_acceleration_is_adjacent_non_overlapping_excess_property(
    sector_t_minus_10: Decimal,
    sector_t_minus_5: Decimal,
    sector_t: Decimal,
    benchmark_t_minus_10: Decimal,
    benchmark_t_minus_5: Decimal,
    benchmark_t: Decimal,
) -> None:
    with localcontext() as context:
        context.prec = 34
        context.rounding = ROUND_HALF_EVEN
        expected = nav_excess_return(
            sector_t_minus_5,
            sector_t,
            benchmark_t_minus_5,
            benchmark_t,
        ) - nav_excess_return(
            sector_t_minus_10,
            sector_t_minus_5,
            benchmark_t_minus_10,
            benchmark_t_minus_5,
        )
    assert (
        nav_relative_acceleration_5d(
            sector_t_minus_10,
            sector_t_minus_5,
            sector_t,
            benchmark_t_minus_10,
            benchmark_t_minus_5,
            benchmark_t,
        )
        == expected
    )


@_PBT_SETTINGS
@given(tied_value=st.integers(-1000, 1000))
def test_tied_midrank_percentile_property(tied_value: int) -> None:
    value = Decimal(tied_value)
    percentiles = descending_midrank_percentiles(
        {
            SectorTicker.XLC: value,
            SectorTicker.XLY: value,
            SectorTicker.XLP: value + Decimal(1),
            SectorTicker.XLE: value - Decimal(1),
        }
    )
    assert percentiles[SectorTicker.XLC] == percentiles[SectorTicker.XLY] == Decimal("0.5")


@_PBT_SETTINGS
@given(
    values=st.lists(
        st.decimals(min_value="0.01", max_value="100000", places=4),
        min_size=21,
        max_size=21,
    )
)
def test_volatility_and_drawdown_bounds_property(values: list[Decimal]) -> None:
    volatility = nav_realized_volatility_20d(values)
    drawdown = nav_max_drawdown_20d(values)
    assert volatility.is_finite() and volatility >= 0
    assert Decimal(-1) <= drawdown <= Decimal(0)


@_PBT_SETTINGS
@given(values=st.lists(st.integers(-1000, 1000), min_size=11, max_size=11))
def test_relative_rank_scores_are_deterministic_and_bounded_property(values: list[int]) -> None:
    metrics = {
        ticker: _metrics_with_excess(
            ticker,
            value_5d=Decimal(values[index]),
            value_21d=Decimal(values[(index + 3) % 11]),
            value_63d=Decimal(values[(index + 7) % 11]),
        )
        for index, ticker in enumerate(SECTOR_TICKERS)
    }

    first = compute_relative_ranks(metrics, coverage_status=SectorCoverageStatus.NORMAL)
    second = compute_relative_ranks(metrics, coverage_status=SectorCoverageStatus.NORMAL)

    assert first == second
    assert {rank.ordinal for rank in first.values()} == set(range(1, 12))
    assert all(
        rank.score is not None and Decimal(0) <= rank.score <= Decimal(1) for rank in first.values()
    )


@pytest.mark.parametrize("size", [0, 1, 20, 22])
def test_window_metrics_reject_non_21_point_input(size: int) -> None:
    navs = [Decimal("100")] * size
    with pytest.raises(ValueError, match="exactly 21"):
        nav_realized_volatility_20d(navs)
    with pytest.raises(ValueError, match="exactly 21"):
        nav_max_drawdown_20d(navs)
