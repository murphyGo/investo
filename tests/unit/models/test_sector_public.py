"""u145 public-sector typed contract tests (TS-1)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from investo.models.sector import (
    PRIMARY_REGIME_POLICY,
    SECTOR_TICKERS,
    AxisState,
    MetricMissingReason,
    MetricValue,
    RegimeResult,
    RelativeRank,
    SectorCoverageStatus,
    SectorRegime,
    SectorTicker,
)
from investo.models.sector_public import (
    PUBLIC_REQUEST_TICKERS,
    PUBLIC_SECTOR_SOURCE_ID,
    PUBLIC_SUPPORTED_SECTOR_TICKERS,
    REQUIRED_PUBLIC_ATTRIBUTIONS,
    YAHOO_FINANCE_ATTRIBUTION,
    FreshnessState,
    MarketScope,
    PublicBarPoint,
    PublicBarSeries,
    PublicCoverageSummary,
    PublicDiagnosticCode,
    PublicMetricName,
    PublicParsedSet,
    PublicSectorBuildOutcome,
    PublicSectorBuildStatus,
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

PBT_SETTINGS = settings(max_examples=50, deadline=None)
_AS_OF = date(2026, 8, 31)
_START = _AS_OF - timedelta(days=63)


def _missing() -> MetricValue:
    return MetricValue(missing_reason=MetricMissingReason.COVERAGE_INSUFFICIENT)


def _metrics(
    ticker: SectorTicker,
    *,
    first_return: MetricValue | None = None,
) -> PublicSectorMetrics:
    missing = _missing()
    return PublicSectorMetrics(
        ticker=ticker,
        price_return_1d=first_return or missing,
        price_return_5d=missing,
        price_return_21d=missing,
        price_return_63d=missing,
        price_excess_1d=missing,
        price_excess_5d=missing,
        price_excess_21d=missing,
        price_excess_63d=missing,
        price_relative_acceleration_5d=missing,
        price_realized_volatility_20d=missing,
        price_max_drawdown_20d=missing,
    )


def _record(ticker: SectorTicker, *, unavailable: bool = False) -> PublicSectorRecord:
    is_xlre = unavailable
    available_order = SECTOR_TICKERS
    complete = MetricValue(value=Decimal("0"))
    return PublicSectorRecord(
        ticker=ticker,
        availability=(
            SectorAvailability.PROVIDER_UNAVAILABLE if is_xlre else SectorAvailability.AVAILABLE
        ),
        metrics=(
            _metrics(ticker)
            if is_xlre
            else PublicSectorMetrics(
                ticker=ticker,
                price_return_1d=complete,
                price_return_5d=complete,
                price_return_21d=complete,
                price_return_63d=complete,
                price_excess_1d=complete,
                price_excess_5d=complete,
                price_excess_21d=complete,
                price_excess_63d=complete,
                price_relative_acceleration_5d=complete,
                price_realized_volatility_20d=complete,
                price_max_drawdown_20d=complete,
            )
        ),
        primary_regime=RegimeResult(
            ticker=ticker,
            regime=SectorRegime.INSUFFICIENT if is_xlre else SectorRegime.LEADING,
            strength_state=None if is_xlre else AxisState.POSITIVE,
            acceleration_state=None if is_xlre else AxisState.POSITIVE,
            policy_id=PRIMARY_REGIME_POLICY.policy_id,
            missing_reason=(MetricMissingReason.COVERAGE_INSUFFICIENT if is_xlre else None),
        ),
        relative_rank=(
            RelativeRank(
                comparable_sector_count=0,
                missing_reason="coverage_insufficient",
            )
            if is_xlre
            else RelativeRank(
                score=Decimal(11 - available_order.index(ticker)) / Decimal(11),
                ordinal=available_order.index(ticker) + 1,
                comparable_sector_count=11,
                used_horizons=(5, 21, 63),
            )
        ),
        diagnostic_codes=((PublicDiagnosticCode.PROVIDER_UNAVAILABLE,) if is_xlre else ()),
    )


def _provenance() -> PublicSourceProvenance:
    return PublicSourceProvenance(target_date=_AS_OF, as_of_date=_AS_OF)


def _coverage() -> PublicCoverageSummary:
    return PublicCoverageSummary(
        status=SectorCoverageStatus.NORMAL,
        available_sector_count=11,
        benchmark_available=True,
        common_as_of=_AS_OF,
        benchmark_observation_count=64,
        missing_tickers=(),
    )


def _snapshot(
    order: tuple[SectorTicker, ...] = SECTOR_TICKERS,
) -> PublicSectorDashboardSnapshot:
    return PublicSectorDashboardSnapshot(
        as_of_date=_AS_OF,
        freshness=FreshnessState.FRESH,
        coverage=_coverage(),
        records=tuple(_record(ticker) for ticker in order),
        provenance=_provenance(),
    )


def _value_series(ticker: SectorTicker, count: int = 64) -> ValueSeries:
    return ValueSeries(
        ticker=ticker,
        points=tuple(
            ValuePoint(
                trading_date=_START + timedelta(days=index),
                value=Decimal(100 + index),
            )
            for index in range(count)
        ),
    )


def _bar_series(ticker: SectorTicker) -> PublicBarSeries:
    points = tuple(
        PublicBarPoint(
            trading_date=_AS_OF - timedelta(days=1 - index),
            open=Decimal("100"),
            high=Decimal("102"),
            low=Decimal("99"),
            close=Decimal("101"),
            volume=1_000,
        )
        for index in range(2)
    )
    return PublicBarSeries(
        ticker=ticker,
        points=points,
        first_date=points[0].trading_date,
        latest_date=points[-1].trading_date,
    )


def test_fixed_source_scope_request_set_and_attributions_are_pinned() -> None:
    assert PUBLIC_SECTOR_SOURCE_ID == "yahoo-chart-daily-v2"
    assert (SectorTicker.SPY, *sorted(SECTOR_TICKERS, key=str)) == PUBLIC_REQUEST_TICKERS
    assert REQUIRED_PUBLIC_ATTRIBUTIONS == (YAHOO_FINANCE_ATTRIBUTION,)
    assert YAHOO_FINANCE_ATTRIBUTION.display_text == "Yahoo Finance — daily ETF price data"
    assert str(YAHOO_FINANCE_ATTRIBUTION.url) == "https://finance.yahoo.com/"
    assert _provenance().schema_version == 2
    assert _provenance().license_ids == ()
    assert _provenance().public_use_permission == "unverified"


@pytest.mark.parametrize(
    "update",
    [
        {"source_id": "another-source"},
        {"market_scope": MarketScope.CONSOLIDATED_US_MARKET},
        {"requested_tickers": tuple(reversed(PUBLIC_REQUEST_TICKERS))},
        {"missing_tickers": (SectorTicker.XLRE,)},
        {"attributions": ()},
    ],
)
def test_provenance_rejects_scope_or_identity_broadening(update: dict[str, object]) -> None:
    payload = _provenance().model_dump()
    payload.update(update)

    with pytest.raises(ValidationError):
        PublicSourceProvenance.model_validate(payload)


def test_attribution_rejects_non_https_url() -> None:
    payload = YAHOO_FINANCE_ATTRIBUTION.model_dump()
    payload["url"] = "http://finance.yahoo.com/"

    with pytest.raises(ValidationError, match="HTTPS"):
        type(YAHOO_FINANCE_ATTRIBUTION).model_validate(payload)


@pytest.mark.parametrize(
    "update",
    [
        {"low": Decimal("101")},
        {"high": Decimal("100")},
        {"close": Decimal("NaN")},
        {"volume": -1},
        {"volume": True},
        {"source": "pitrading"},
    ],
)
def test_public_bar_rejects_invalid_or_non_yahoo_rows(update: dict[str, object]) -> None:
    payload: dict[str, object] = {
        "trading_date": _AS_OF,
        "open": Decimal("100"),
        "high": Decimal("102"),
        "low": Decimal("99"),
        "close": Decimal("101"),
        "volume": 1_000,
    }
    payload.update(update)

    with pytest.raises(ValidationError):
        PublicBarPoint.model_validate(payload)


def test_parsed_set_accounts_for_exact_request_set_including_xlre() -> None:
    benchmark = _bar_series(SectorTicker.SPY)
    sectors = {ticker: _bar_series(ticker) for ticker in PUBLIC_SUPPORTED_SECTOR_TICKERS}
    parsed = PublicParsedSet(benchmark=benchmark, sectors=sectors)

    assert tuple(parsed.sectors) == PUBLIC_SUPPORTED_SECTOR_TICKERS
    assert PublicParsedSet.model_validate_json(parsed.model_dump_json()) == parsed
    with pytest.raises(ValidationError, match="account for"):
        PublicParsedSet(
            benchmark=benchmark,
            sectors={
                ticker: series
                for ticker, series in sectors.items()
                if ticker is not SectorTicker.XLY
            },
        )
    with pytest.raises(ValidationError):
        PublicParsedSet(
            benchmark=benchmark,
            sectors=sectors,
            failures=(
                PublicSourceFailure(
                    ticker=SectorTicker.XLRE,
                    issue_code=PublicSourceIssueCode.STATUS,
                    retryable=False,
                ),
            ),
        )


def test_close_only_bundle_includes_xlre_and_same_as_of() -> None:
    benchmark = _value_series(SectorTicker.SPY)
    sectors = tuple(_value_series(ticker) for ticker in PUBLIC_SUPPORTED_SECTOR_TICKERS)
    bundle = PublicSectorSeriesBundle(
        as_of_date=_AS_OF,
        benchmark=benchmark,
        sectors=sectors,
        coverage=_coverage(),
        provenance=_provenance(),
    )

    assert tuple(series.ticker for series in bundle.sectors) == SECTOR_TICKERS
    assert bundle.coverage.missing_tickers == ()
    assert "open" not in bundle.model_dump_json()
    with pytest.raises(ValidationError):
        PublicSectorSeriesBundle(
            as_of_date=_AS_OF,
            benchmark=benchmark,
            sectors=(*sectors, _value_series(SectorTicker.XLRE)),
            coverage=_coverage(),
            provenance=_provenance(),
        )


def test_public_coverage_keeps_22_to_63_rows_in_warming_up() -> None:
    warming = PublicCoverageSummary(
        status=SectorCoverageStatus.WARMING_UP,
        available_sector_count=10,
        benchmark_available=True,
        common_as_of=_AS_OF,
        benchmark_observation_count=63,
        missing_tickers=(SectorTicker.XLRE,),
    )

    assert warming.status is SectorCoverageStatus.WARMING_UP
    with pytest.raises(ValidationError, match="64 rows"):
        PublicCoverageSummary(
            status=SectorCoverageStatus.PARTIAL,
            available_sector_count=10,
            benchmark_available=True,
            common_as_of=_AS_OF,
            benchmark_observation_count=63,
            missing_tickers=(SectorTicker.XLRE,),
        )


def test_snapshot_is_fixed_scope_derived_only_and_includes_xlre() -> None:
    snapshot = _snapshot()
    xlre = next(record for record in snapshot.records if record.ticker is SectorTicker.XLRE)

    assert snapshot.market_scope is MarketScope.PROVIDER_REPORTED_US_EQUITY
    assert snapshot.actual_market_ohlcv is True
    assert snapshot.consolidated_market_data is False
    assert xlre.availability is SectorAvailability.AVAILABLE
    assert all(
        getattr(xlre.metrics, metric_name.value).value is not None
        for metric_name in PublicMetricName
    )
    payload = snapshot.model_dump_json()
    assert "points" not in payload
    assert "volume" not in payload
    assert PublicSectorDashboardSnapshot.model_validate_json(payload) == snapshot


def test_partial_snapshot_rejects_available_record_with_missing_metrics() -> None:
    records = list(_snapshot().records)
    xlc_index = SECTOR_TICKERS.index(SectorTicker.XLC)
    records[xlc_index] = records[xlc_index].model_copy(
        update={"metrics": _metrics(SectorTicker.XLC)}
    )

    with pytest.raises(ValidationError, match="every metric"):
        PublicSectorDashboardSnapshot(
            as_of_date=_AS_OF,
            freshness=FreshnessState.FRESH,
            coverage=_coverage(),
            records=tuple(records),
            provenance=_provenance(),
        )


def test_xlre_or_unavailable_metric_leakage_is_rejected() -> None:
    with pytest.raises(ValidationError, match="suppress every metric"):
        PublicSectorRecord(
            ticker=SectorTicker.XLRE,
            availability=SectorAvailability.PROVIDER_UNAVAILABLE,
            metrics=_metrics(
                SectorTicker.XLRE,
                first_return=MetricValue(value=Decimal("0.01")),
            ),
            primary_regime=_record(SectorTicker.XLRE, unavailable=True).primary_regime,
            relative_rank=_record(SectorTicker.XLRE, unavailable=True).relative_rank,
            diagnostic_codes=(PublicDiagnosticCode.PROVIDER_UNAVAILABLE,),
        )

    with pytest.raises(ValidationError, match="suppress every metric"):
        PublicSectorRecord(
            ticker=SectorTicker.XLC,
            availability=SectorAvailability.INSUFFICIENT_HISTORY,
            metrics=_metrics(
                SectorTicker.XLC,
                first_return=MetricValue(value=Decimal("0.01")),
            ),
            primary_regime=_record(SectorTicker.XLRE, unavailable=True).primary_regime.model_copy(
                update={"ticker": SectorTicker.XLC}
            ),
            relative_rank=_record(SectorTicker.XLRE, unavailable=True).relative_rank,
            diagnostic_codes=(PublicDiagnosticCode.INSUFFICIENT_HISTORY,),
        )


def test_insufficient_history_record_must_appear_in_coverage_missing_set() -> None:
    records = list(_snapshot().records)
    xlc_index = SECTOR_TICKERS.index(SectorTicker.XLC)
    records[xlc_index] = PublicSectorRecord(
        ticker=SectorTicker.XLC,
        availability=SectorAvailability.INSUFFICIENT_HISTORY,
        metrics=_metrics(SectorTicker.XLC),
        primary_regime=_record(SectorTicker.XLRE, unavailable=True).primary_regime.model_copy(
            update={"ticker": SectorTicker.XLC}
        ),
        relative_rank=_record(SectorTicker.XLRE, unavailable=True).relative_rank,
        diagnostic_codes=(PublicDiagnosticCode.INSUFFICIENT_HISTORY,),
    )

    with pytest.raises(ValidationError, match="missing_tickers"):
        PublicSectorDashboardSnapshot(
            as_of_date=_AS_OF,
            freshness=FreshnessState.FRESH,
            coverage=_coverage(),
            records=tuple(records),
            provenance=_provenance(),
        )


@given(order=st.permutations(SECTOR_TICKERS))
@PBT_SETTINGS
def test_public_snapshot_round_trip_and_order_are_stable(order: list[SectorTicker]) -> None:
    snapshot = _snapshot(tuple(order))
    reference = _snapshot()

    assert tuple(record.ticker for record in snapshot.records) == SECTOR_TICKERS
    assert snapshot.model_dump_json() == reference.model_dump_json()
    assert PublicSectorDashboardSnapshot.model_validate_json(snapshot.model_dump_json()) == snapshot


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
        max_size=80,
    ),
    start=st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 1, 1)),
)
@PBT_SETTINGS
def test_value_series_round_trip_preserves_order(values: list[Decimal], start: date) -> None:
    points = tuple(
        ValuePoint(trading_date=start + timedelta(days=index), value=value)
        for index, value in enumerate(values)
    )
    series = ValueSeries(ticker=SectorTicker.XLK, points=points)

    assert series.first_date == points[0].trading_date
    assert series.latest_date == points[-1].trading_date
    assert ValueSeries.model_validate_json(series.model_dump_json()) == series


@pytest.mark.parametrize(
    ("status", "has_identity", "has_failures"),
    [
        (PublicSectorBuildStatus.PROMOTED, True, False),
        (PublicSectorBuildStatus.UNCHANGED, True, False),
        (PublicSectorBuildStatus.HELD_LAST_GOOD, True, True),
        (PublicSectorBuildStatus.BLOCKED, False, True),
    ],
)
def test_build_outcome_closed_variants(
    status: PublicSectorBuildStatus,
    has_identity: bool,
    has_failures: bool,
) -> None:
    outcome = PublicSectorBuildOutcome(
        status=status,
        snapshot_id="sha256:" + "a" * 64 if has_identity else None,
        as_of_date=_AS_OF if has_identity else None,
        failure_codes=(PublicDiagnosticCode.BENCHMARK_UNAVAILABLE,) if has_failures else (),
    )

    assert outcome.status is status
