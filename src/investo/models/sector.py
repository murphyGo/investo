"""Typed contracts for the private US sector core-radar validation.

This is the shared, side-effect-free model surface for u139.  It contains
neither workbook parsing nor rendering and imports no Investo work component.
The existing ``models.CoverageStatus`` belongs to briefing segments, so the
sector-specific state is named :class:`SectorCoverageStatus` at package scope.

References: FR-022, NFR-008, u139 FD E1-E21 and NFR AC-4.1-AC-4.7.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation, localcontext
from enum import StrEnum
from itertools import pairwise
from pathlib import Path
from types import MappingProxyType
from typing import Final, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

SECTOR_UNIVERSE_VERSION: Final[Literal["select-sector-spdr-v1"]] = "select-sector-spdr-v1"
SECTOR_SOURCE_ID: Final[Literal["state-street-nav-history-private"]] = (
    "state-street-nav-history-private"
)
METRIC_QUANTUM: Final[Decimal] = Decimal("0.0000000001")
REGIME_BANDS_BPS: Final[tuple[int, ...]] = (0, 5, 10, 15, 20)
RankHorizon = Literal[5, 21, 63]
RANK_HORIZONS: Final[tuple[RankHorizon, ...]] = (5, 21, 63)


class SectorTicker(StrEnum):
    """Closed identity set for the eleven sectors and SPY benchmark."""

    XLC = "XLC"
    XLY = "XLY"
    XLP = "XLP"
    XLE = "XLE"
    XLF = "XLF"
    XLV = "XLV"
    XLI = "XLI"
    XLB = "XLB"
    XLRE = "XLRE"
    XLK = "XLK"
    XLU = "XLU"
    SPY = "SPY"


SECTOR_TICKERS: Final[tuple[SectorTicker, ...]] = (
    SectorTicker.XLC,
    SectorTicker.XLY,
    SectorTicker.XLP,
    SectorTicker.XLE,
    SectorTicker.XLF,
    SectorTicker.XLV,
    SectorTicker.XLI,
    SectorTicker.XLB,
    SectorTicker.XLRE,
    SectorTicker.XLK,
    SectorTicker.XLU,
)
BENCHMARK_TICKER: Final[SectorTicker] = SectorTicker.SPY
ALL_SECTOR_TICKERS: Final[tuple[SectorTicker, ...]] = (*SECTOR_TICKERS, BENCHMARK_TICKER)
_TICKER_POSITION: Final[dict[SectorTicker, int]] = {
    ticker: position for position, ticker in enumerate(ALL_SECTOR_TICKERS)
}


class WorkbookIssueCode(StrEnum):
    OPEN = "workbook.open"
    HEADER = "workbook.header"
    DATE = "workbook.date"
    NAV = "workbook.nav"
    ORDER = "workbook.order"
    DUPLICATE_DATE = "workbook.duplicate_date"


class DiagnosticIssueCode(StrEnum):
    MANIFEST_SCHEMA = "manifest.schema"
    MANIFEST_UNIVERSE = "manifest.universe"
    MANIFEST_PATH = "manifest.path"
    OUTPUT_FORBIDDEN_PATH = "output.forbidden_path"
    WORKBOOK_OPEN = "workbook.open"
    WORKBOOK_HEADER = "workbook.header"
    WORKBOOK_DATE = "workbook.date"
    WORKBOOK_NAV = "workbook.nav"
    WORKBOOK_ORDER = "workbook.order"
    WORKBOOK_DUPLICATE_DATE = "workbook.duplicate_date"
    BUNDLE_SPY_MISSING = "bundle.spy_missing"
    BUNDLE_AS_OF_MISMATCH = "bundle.as_of_mismatch"
    BUNDLE_COVERAGE_INSUFFICIENT = "bundle.coverage_insufficient"
    METRIC_INSUFFICIENT_HISTORY = "metric.insufficient_history"


class SectorCoverageStatus(StrEnum):
    NORMAL = "normal"
    PARTIAL = "partial"
    WARMING_UP = "warming_up"
    INSUFFICIENT = "insufficient"


class MetricMissingReason(StrEnum):
    COVERAGE_INSUFFICIENT = "coverage_insufficient"
    WARMING_UP = "warming_up"
    BENCHMARK_DATE_MISSING = "benchmark_date_missing"
    SECTOR_DATE_MISSING = "sector_date_missing"
    INSUFFICIENT_HISTORY = "insufficient_history"
    NUMERIC_INVALID = "numeric_invalid"


class SectorMetricName(StrEnum):
    """Closed identifiers allowed on the redacted metric diagnostic surface."""

    NAV_RETURN_1D = "nav_return_1d"
    NAV_RETURN_5D = "nav_return_5d"
    NAV_RETURN_21D = "nav_return_21d"
    NAV_RETURN_63D = "nav_return_63d"
    NAV_EXCESS_1D = "nav_excess_1d"
    NAV_EXCESS_5D = "nav_excess_5d"
    NAV_EXCESS_21D = "nav_excess_21d"
    NAV_EXCESS_63D = "nav_excess_63d"
    NAV_RELATIVE_ACCELERATION_5D = "nav_relative_acceleration_5d"
    NAV_REALIZED_VOLATILITY_20D = "nav_realized_volatility_20d"
    NAV_MAX_DRAWDOWN_20D = "nav_max_drawdown_20d"


class AxisState(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"


class SectorRegime(StrEnum):
    LEADING = "leading"
    WEAKENING = "weakening"
    RECOVERING = "recovering"
    LAGGING = "lagging"
    INSUFFICIENT = "insufficient"


_REGIME_BY_AXES: Final[dict[tuple[AxisState, AxisState], SectorRegime]] = {
    (AxisState.POSITIVE, AxisState.POSITIVE): SectorRegime.LEADING,
    (AxisState.POSITIVE, AxisState.NEGATIVE): SectorRegime.WEAKENING,
    (AxisState.NEGATIVE, AxisState.POSITIVE): SectorRegime.RECOVERING,
    (AxisState.NEGATIVE, AxisState.NEGATIVE): SectorRegime.LAGGING,
}


class SectorUniverse(BaseModel):
    """The immutable fixed universe used by every u139 layer."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sectors: tuple[SectorTicker, ...] = SECTOR_TICKERS
    benchmark: SectorTicker = BENCHMARK_TICKER
    version: Literal["select-sector-spdr-v1"] = SECTOR_UNIVERSE_VERSION

    @model_validator(mode="after")
    def _validate_fixed_identity(self) -> Self:
        if self.sectors != SECTOR_TICKERS:
            raise ValueError("sectors must equal the fixed Select Sector SPDR order")
        if self.benchmark is not BENCHMARK_TICKER:
            raise ValueError("benchmark must be SPY")
        return self


FIXED_SECTOR_UNIVERSE: Final[SectorUniverse] = SectorUniverse()


class PrivateWorkbookManifest(BaseModel):
    """Explicit private ticker-to-workbook mapping; never an output DTO."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[1]
    workbooks: Mapping[SectorTicker, Path]

    @field_validator("workbooks")
    @classmethod
    def _validate_workbooks(cls, value: Mapping[SectorTicker, Path]) -> Mapping[SectorTicker, Path]:
        if set(value) != set(ALL_SECTOR_TICKERS):
            raise ValueError("workbooks must contain the exact fixed twelve-ticker universe")
        paths = tuple(value[ticker] for ticker in ALL_SECTOR_TICKERS)
        if any(not path.is_absolute() for path in paths):
            raise ValueError("workbook paths must be absolute")
        if any(path.suffix.lower() != ".xlsx" for path in paths):
            raise ValueError("workbook paths must use the .xlsx suffix")
        if len({str(path) for path in paths}) != len(paths):
            raise ValueError("workbook paths must be unique")
        return MappingProxyType({ticker: value[ticker] for ticker in ALL_SECTOR_TICKERS})

    @field_serializer("workbooks")
    def _serialize_workbooks(self, value: Mapping[SectorTicker, Path]) -> dict[SectorTicker, Path]:
        return dict(value)


class NavPoint(BaseModel):
    """One canonical positive NAV observation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    trading_date: date
    nav: Decimal

    @field_validator("trading_date", mode="before")
    @classmethod
    def _validate_date_only(cls, value: object) -> date:
        if isinstance(value, datetime):
            raise ValueError("trading_date must not contain time or timezone data")
        if isinstance(value, str):
            try:
                parsed = date.fromisoformat(value)
            except ValueError as exc:
                raise ValueError("trading_date must use YYYY-MM-DD") from exc
            if value != parsed.isoformat():
                raise ValueError("trading_date must use canonical YYYY-MM-DD")
            return parsed
        if not isinstance(value, date):
            raise ValueError("trading_date must be a date")
        return value

    @field_validator("nav", mode="before")
    @classmethod
    def _reject_boolean_nav(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("NAV must be numeric, not boolean")
        return value

    @field_validator("nav")
    @classmethod
    def _validate_nav(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value <= 0:
            raise ValueError("NAV must be finite and strictly positive")
        return value


class NavSeries(BaseModel):
    """One strictly ascending canonical NAV series."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ticker: SectorTicker
    points: tuple[NavPoint, ...] = Field(min_length=2)
    first_date: date
    latest_date: date

    @model_validator(mode="after")
    def _validate_series(self) -> Self:
        dates = tuple(point.trading_date for point in self.points)
        if any(current >= following for current, following in pairwise(dates)):
            raise ValueError("NAV points must be strictly ascending with unique dates")
        if self.first_date != dates[0] or self.latest_date != dates[-1]:
            raise ValueError("first_date/latest_date must equal point endpoints")
        return self


class WorkbookFailure(BaseModel):
    """Redacted ticker-scoped workbook failure."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ticker: SectorTicker
    issue_code: WorkbookIssueCode
    row_count: int | None = Field(default=None, ge=0)
    first_date: date | None = None
    latest_date: date | None = None

    @model_validator(mode="after")
    def _validate_date_range(self) -> Self:
        if (
            self.first_date is not None
            and self.latest_date is not None
            and self.first_date > self.latest_date
        ):
            raise ValueError("first_date must not be after latest_date")
        return self


class CoverageSummary(BaseModel):
    """Sector-only availability plus the separate mandatory benchmark state."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: SectorCoverageStatus
    available_sector_count: int = Field(ge=0, le=11)
    expected_sector_count: Literal[11] = 11
    benchmark_available: bool
    common_as_of: date | None = None
    benchmark_observation_count: int = Field(ge=0)
    missing_tickers: tuple[SectorTicker, ...] = ()
    reason_codes: tuple[DiagnosticIssueCode, ...] = ()

    @field_validator("missing_tickers")
    @classmethod
    def _normalize_missing(cls, value: tuple[SectorTicker, ...]) -> tuple[SectorTicker, ...]:
        if BENCHMARK_TICKER in value:
            raise ValueError("missing_tickers counts sectors only")
        if len(set(value)) != len(value):
            raise ValueError("missing_tickers must be unique")
        return tuple(ticker for ticker in SECTOR_TICKERS if ticker in value)

    @field_validator("reason_codes")
    @classmethod
    def _normalize_reasons(
        cls, value: tuple[DiagnosticIssueCode, ...]
    ) -> tuple[DiagnosticIssueCode, ...]:
        return tuple(sorted(set(value), key=str))

    @model_validator(mode="after")
    def _validate_coverage(self) -> Self:
        if self.available_sector_count + len(self.missing_tickers) != 11:
            raise ValueError("available and missing sector counts must total eleven")
        if not self.benchmark_available and self.benchmark_observation_count != 0:
            raise ValueError("unavailable benchmark must have zero observations")
        if self.status is SectorCoverageStatus.NORMAL:
            if not (
                self.benchmark_available
                and self.common_as_of is not None
                and self.available_sector_count == 11
                and self.benchmark_observation_count >= 22
            ):
                raise ValueError("normal coverage requires SPY, 11 sectors, as-of, and 22 rows")
        elif self.status is SectorCoverageStatus.PARTIAL:
            if not (
                self.benchmark_available
                and self.common_as_of is not None
                and 8 <= self.available_sector_count <= 10
                and self.benchmark_observation_count >= 22
            ):
                raise ValueError("partial coverage requires SPY, 8-10 sectors, and 22 rows")
        elif self.status is SectorCoverageStatus.WARMING_UP and not (
            self.benchmark_available
            and self.common_as_of is not None
            and self.available_sector_count >= 8
            and 6 <= self.benchmark_observation_count <= 21
        ):
            raise ValueError("warming_up requires SPY, at least 8 sectors, and 6-21 rows")
        return self


class PrivateDiagnostic(BaseModel):
    """Closed, redacted diagnostic surface."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    issue_code: DiagnosticIssueCode
    ticker: SectorTicker | None = None
    metric_name: SectorMetricName | None = None
    row_count: int | None = Field(default=None, ge=0)
    first_date: date | None = None
    latest_date: date | None = None

    @model_validator(mode="after")
    def _validate_date_range(self) -> Self:
        if (
            self.first_date is not None
            and self.latest_date is not None
            and self.first_date > self.latest_date
        ):
            raise ValueError("first_date must not be after latest_date")
        return self


class ParsedWorkbookSet(BaseModel):
    """Exactly one parse success or redacted failure per fixed identity."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    series_by_ticker: Mapping[SectorTicker, NavSeries]
    failures: tuple[WorkbookFailure, ...] = ()

    @field_validator("series_by_ticker")
    @classmethod
    def _normalize_series(
        cls, value: Mapping[SectorTicker, NavSeries]
    ) -> Mapping[SectorTicker, NavSeries]:
        for ticker, series in value.items():
            if ticker is not series.ticker:
                raise ValueError("series mapping key must match series ticker")
        return MappingProxyType(
            {ticker: value[ticker] for ticker in ALL_SECTOR_TICKERS if ticker in value}
        )

    @field_serializer("series_by_ticker")
    def _serialize_series_by_ticker(
        self, value: Mapping[SectorTicker, NavSeries]
    ) -> dict[SectorTicker, NavSeries]:
        return dict(value)

    @field_validator("failures")
    @classmethod
    def _normalize_failures(cls, value: tuple[WorkbookFailure, ...]) -> tuple[WorkbookFailure, ...]:
        if len({failure.ticker for failure in value}) != len(value):
            raise ValueError("failures must contain unique tickers")
        return tuple(sorted(value, key=lambda failure: _TICKER_POSITION[failure.ticker]))

    @model_validator(mode="after")
    def _validate_identity_partition(self) -> Self:
        successes = set(self.series_by_ticker)
        failures = {failure.ticker for failure in self.failures}
        if successes & failures:
            raise ValueError("ticker cannot be both parse success and failure")
        if successes | failures != set(ALL_SECTOR_TICKERS):
            raise ValueError("parsed set must account for all twelve tickers")
        return self


_FINGERPRINT_PATTERN: Final[str] = r"^sha256:[0-9a-f]{64}$"


class SectorSeriesBundle(BaseModel):
    """Canonical same-as-of input to pure metric and regime functions."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    universe_version: Literal["select-sector-spdr-v1"] = SECTOR_UNIVERSE_VERSION
    input_kind: Literal["nav"] = "nav"
    source_id: Literal["state-street-nav-history-private"] = SECTOR_SOURCE_ID
    as_of_date: date | None = None
    benchmark: NavSeries | None = None
    sectors: tuple[NavSeries, ...] = ()
    coverage: CoverageSummary
    diagnostics: tuple[PrivateDiagnostic, ...] = ()
    input_fingerprint: str | None = Field(default=None, pattern=_FINGERPRINT_PATTERN)

    @field_validator("sectors")
    @classmethod
    def _normalize_sectors(cls, value: tuple[NavSeries, ...]) -> tuple[NavSeries, ...]:
        if any(series.ticker is BENCHMARK_TICKER for series in value):
            raise ValueError("SPY belongs in benchmark, not sectors")
        if len({series.ticker for series in value}) != len(value):
            raise ValueError("sector series must have unique tickers")
        return tuple(sorted(value, key=lambda series: _TICKER_POSITION[series.ticker]))

    @field_validator("diagnostics")
    @classmethod
    def _normalize_diagnostics(
        cls, value: tuple[PrivateDiagnostic, ...]
    ) -> tuple[PrivateDiagnostic, ...]:
        return tuple(sorted(value, key=_diagnostic_sort_key))

    @model_validator(mode="after")
    def _validate_bundle(self) -> Self:
        if self.coverage.available_sector_count != len(self.sectors):
            raise ValueError("coverage count must match available sector series")
        available = {series.ticker for series in self.sectors}
        if set(self.coverage.missing_tickers) != set(SECTOR_TICKERS) - available:
            raise ValueError("coverage missing_tickers must complement available series")
        if self.coverage.benchmark_available != (self.benchmark is not None):
            raise ValueError("coverage benchmark flag must match benchmark series")
        benchmark_observation_count = (
            len(self.benchmark.points) if self.benchmark is not None else 0
        )
        if self.coverage.benchmark_observation_count != benchmark_observation_count:
            raise ValueError("coverage benchmark count must match benchmark series")
        if self.benchmark is not None and self.benchmark.ticker is not BENCHMARK_TICKER:
            raise ValueError("benchmark series must be SPY")
        if self.as_of_date != self.coverage.common_as_of:
            raise ValueError("bundle as_of_date must equal coverage common_as_of")
        if self.as_of_date is not None:
            series = (*self.sectors, *((self.benchmark,) if self.benchmark is not None else ()))
            if any(item.latest_date != self.as_of_date for item in series):
                raise ValueError("all metric-bearing series must share the bundle as-of date")
        return self


def _quantize_ratio(value: Decimal) -> Decimal:
    if not value.is_finite():
        raise ValueError("metric value must be finite")
    try:
        with localcontext() as context:
            context.prec = 34
            result = value.quantize(METRIC_QUANTUM, rounding=ROUND_HALF_EVEN)
    except InvalidOperation as exc:
        raise ValueError("metric value exceeds decimal precision contract") from exc
    if result == 0:
        return Decimal("0.0000000000")
    return result


class MetricValue(BaseModel):
    """One quantized ratio or one explicit missing reason."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    value: Decimal | None = None
    missing_reason: MetricMissingReason | None = None

    @field_validator("value", mode="before")
    @classmethod
    def _reject_boolean_value(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("metric value must be numeric, not boolean")
        return value

    @field_validator("value")
    @classmethod
    def _normalize_value(cls, value: Decimal | None) -> Decimal | None:
        return None if value is None else _quantize_ratio(value)

    @model_validator(mode="after")
    def _validate_exclusive_state(self) -> Self:
        if (self.value is None) == (self.missing_reason is None):
            raise ValueError("exactly one of value and missing_reason is required")
        return self


class SectorMetrics(BaseModel):
    """All deterministic NAV metric slots for one sector."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ticker: SectorTicker
    nav_return_1d: MetricValue
    nav_return_5d: MetricValue
    nav_return_21d: MetricValue
    nav_return_63d: MetricValue
    nav_excess_1d: MetricValue
    nav_excess_5d: MetricValue
    nav_excess_21d: MetricValue
    nav_excess_63d: MetricValue
    nav_relative_acceleration_5d: MetricValue
    nav_realized_volatility_20d: MetricValue
    nav_max_drawdown_20d: MetricValue


class RegimePolicy(BaseModel):
    """Versioned neutral-band policy."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    policy_id: str = Field(min_length=1, max_length=64)
    neutral_band_bps: Literal[0, 5, 10, 15, 20]
    relative_horizon: Literal[21] = 21
    acceleration_horizon: Literal[5] = 5
    hysteresis: Literal[True] = True

    @model_validator(mode="after")
    def _validate_policy_id(self) -> Self:
        primary = self.neutral_band_bps == 10 and self.policy_id == "sector-regime-v1"
        sensitivity = self.policy_id == f"sector-regime-v1-band-{self.neutral_band_bps}"
        if not (primary or sensitivity):
            raise ValueError("policy_id must match the selected neutral band")
        return self


PRIMARY_REGIME_POLICY: Final[RegimePolicy] = RegimePolicy(
    policy_id="sector-regime-v1",
    neutral_band_bps=10,
)


class RegimeResult(BaseModel):
    """Primary or sensitivity regime for one sector."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ticker: SectorTicker
    regime: SectorRegime
    strength_state: AxisState | None = None
    acceleration_state: AxisState | None = None
    policy_id: str = Field(min_length=1, max_length=64)
    missing_reason: MetricMissingReason | None = None

    @model_validator(mode="after")
    def _validate_regime_state(self) -> Self:
        if self.regime is SectorRegime.INSUFFICIENT:
            if (
                self.strength_state is not None
                or self.acceleration_state is not None
                or self.missing_reason is None
            ):
                raise ValueError("insufficient regime requires only a missing reason")
        elif (
            self.strength_state is None
            or self.acceleration_state is None
            or self.missing_reason is not None
        ):
            raise ValueError("complete regime requires both axis states and no missing reason")
        elif self.regime is not _REGIME_BY_AXES[(self.strength_state, self.acceleration_state)]:
            raise ValueError("regime must match its strength and acceleration axis states")
        return self


class RelativeRank(BaseModel):
    """Deterministic cross-sectional rank result."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    score: Decimal | None = None
    ordinal: int | None = Field(default=None, ge=1, le=11)
    comparable_sector_count: int = Field(ge=0, le=11)
    used_horizons: tuple[RankHorizon, ...] = ()
    missing_reason: str | None = Field(default=None, min_length=1, max_length=80)

    @field_validator("score", mode="before")
    @classmethod
    def _reject_boolean_score(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("rank score must be numeric, not boolean")
        return value

    @field_validator("score")
    @classmethod
    def _normalize_score(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        normalized = _quantize_ratio(value)
        if not Decimal(0) <= normalized <= Decimal(1):
            raise ValueError("rank score must be in [0, 1]")
        return normalized

    @field_validator("used_horizons")
    @classmethod
    def _normalize_horizons(cls, value: tuple[RankHorizon, ...]) -> tuple[RankHorizon, ...]:
        if len(set(value)) != len(value):
            raise ValueError("used_horizons must be unique")
        return tuple(horizon for horizon in RANK_HORIZONS if horizon in value)

    @model_validator(mode="after")
    def _validate_rank_state(self) -> Self:
        if self.score is None:
            if self.ordinal is not None or self.missing_reason is None:
                raise ValueError("missing rank requires no ordinal and a missing reason")
        elif (
            self.ordinal is None
            or self.missing_reason is not None
            or self.comparable_sector_count < 8
            or len(self.used_horizons) < 2
            or self.ordinal > self.comparable_sector_count
        ):
            raise ValueError("rank requires ordinal, 8 comparables, and at least two horizons")
        return self


class SectorRecord(BaseModel):
    """One sector's complete snapshot record."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ticker: SectorTicker
    metrics: SectorMetrics
    primary_regime: RegimeResult
    sensitivity_regimes: Mapping[int, SectorRegime]
    relative_rank: RelativeRank
    diagnostic_codes: tuple[DiagnosticIssueCode, ...] = ()

    @field_validator("sensitivity_regimes")
    @classmethod
    def _normalize_sensitivity(
        cls, value: Mapping[int, SectorRegime]
    ) -> Mapping[int, SectorRegime]:
        if set(value) != set(REGIME_BANDS_BPS):
            raise ValueError("sensitivity_regimes must contain 0/5/10/15/20 bps")
        return MappingProxyType({band: value[band] for band in REGIME_BANDS_BPS})

    @field_serializer("sensitivity_regimes")
    def _serialize_sensitivity(self, value: Mapping[int, SectorRegime]) -> dict[int, SectorRegime]:
        return dict(value)

    @field_validator("diagnostic_codes")
    @classmethod
    def _normalize_diagnostic_codes(
        cls, value: tuple[DiagnosticIssueCode, ...]
    ) -> tuple[DiagnosticIssueCode, ...]:
        return tuple(sorted(set(value), key=str))

    @model_validator(mode="after")
    def _validate_record_identity(self) -> Self:
        if self.ticker is BENCHMARK_TICKER:
            raise ValueError("sector records cannot use SPY")
        if self.metrics.ticker is not self.ticker or self.primary_regime.ticker is not self.ticker:
            raise ValueError("nested ticker identities must match the sector record")
        if self.primary_regime.policy_id != PRIMARY_REGIME_POLICY.policy_id:
            raise ValueError("primary regime must use sector-regime-v1")
        if self.sensitivity_regimes[10] is not self.primary_regime.regime:
            raise ValueError("10 bps sensitivity must equal the primary regime")
        return self


_WARMING_SUPPRESSED_METRICS: Final[tuple[SectorMetricName, ...]] = (
    SectorMetricName.NAV_RETURN_21D,
    SectorMetricName.NAV_RETURN_63D,
    SectorMetricName.NAV_EXCESS_21D,
    SectorMetricName.NAV_EXCESS_63D,
    SectorMetricName.NAV_RELATIVE_ACCELERATION_5D,
    SectorMetricName.NAV_REALIZED_VOLATILITY_20D,
    SectorMetricName.NAV_MAX_DRAWDOWN_20D,
)
_ALL_METRIC_FIELDS: Final[tuple[SectorMetricName, ...]] = tuple(SectorMetricName)


class SectorDashboardSnapshot(BaseModel):
    """Immutable machine snapshot; projection populates ``snapshot_id`` later."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[1] = 1
    snapshot_id: str | None = Field(default=None, pattern=_FINGERPRINT_PATTERN)
    universe_version: Literal["select-sector-spdr-v1"] = SECTOR_UNIVERSE_VERSION
    input_kind: Literal["nav"] = "nav"
    source_id: Literal["state-street-nav-history-private"] = SECTOR_SOURCE_ID
    private_validation: Literal[True] = True
    actual_market_ohlcv: Literal[False] = False
    as_of_date: date | None = None
    coverage: CoverageSummary
    primary_policy: RegimePolicy = PRIMARY_REGIME_POLICY
    records: tuple[SectorRecord, ...]
    diagnostics: tuple[PrivateDiagnostic, ...] = ()
    input_fingerprint: str | None = Field(default=None, pattern=_FINGERPRINT_PATTERN)

    @field_validator("records")
    @classmethod
    def _normalize_records(cls, value: tuple[SectorRecord, ...]) -> tuple[SectorRecord, ...]:
        if len(value) != 11 or {record.ticker for record in value} != set(SECTOR_TICKERS):
            raise ValueError("snapshot must contain exactly the eleven sector records")
        return tuple(sorted(value, key=_record_sort_key))

    @field_validator("diagnostics")
    @classmethod
    def _normalize_diagnostics(
        cls, value: tuple[PrivateDiagnostic, ...]
    ) -> tuple[PrivateDiagnostic, ...]:
        return tuple(sorted(value, key=_diagnostic_sort_key))

    @model_validator(mode="after")
    def _validate_snapshot_state(self) -> Self:
        if self.as_of_date != self.coverage.common_as_of:
            raise ValueError("snapshot as_of_date must equal coverage common_as_of")
        if self.primary_policy != PRIMARY_REGIME_POLICY:
            raise ValueError("snapshot primary policy must be sector-regime-v1 at 10 bps")
        missing_tickers = set(self.coverage.missing_tickers)
        for record in self.records:
            if record.ticker not in missing_tickers:
                continue
            if any(getattr(record.metrics, name).value is not None for name in _ALL_METRIC_FIELDS):
                raise ValueError("missing sectors must suppress every metric value")
            if (
                record.primary_regime.regime is not SectorRegime.INSUFFICIENT
                or any(
                    regime is not SectorRegime.INSUFFICIENT
                    for regime in record.sensitivity_regimes.values()
                )
                or record.relative_rank.score is not None
            ):
                raise ValueError("missing sectors must suppress regime and rank")
        if self.coverage.status is SectorCoverageStatus.INSUFFICIENT:
            for record in self.records:
                if any(
                    getattr(record.metrics, name).value is not None for name in _ALL_METRIC_FIELDS
                ):
                    raise ValueError("insufficient snapshots must suppress every metric value")
                if (
                    record.primary_regime.regime is not SectorRegime.INSUFFICIENT
                    or any(
                        regime is not SectorRegime.INSUFFICIENT
                        for regime in record.sensitivity_regimes.values()
                    )
                    or record.relative_rank.score is not None
                ):
                    raise ValueError("insufficient snapshots must suppress regime and rank")
        elif self.coverage.status is SectorCoverageStatus.WARMING_UP:
            for record in self.records:
                if any(
                    getattr(record.metrics, name).value is not None
                    for name in _WARMING_SUPPRESSED_METRICS
                ):
                    raise ValueError("warming_up snapshots may expose only 1D/5D metrics")
                if (
                    record.primary_regime.regime is not SectorRegime.INSUFFICIENT
                    or any(
                        regime is not SectorRegime.INSUFFICIENT
                        for regime in record.sensitivity_regimes.values()
                    )
                    or record.relative_rank.score is not None
                ):
                    raise ValueError("warming_up snapshots must suppress regime and rank")
        return self


class PrivateArtifactSet(BaseModel):
    """Resolved paths for one private projection pair."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    snapshot_path: Path
    report_path: Path

    @model_validator(mode="after")
    def _validate_pair_shape(self) -> Self:
        if not self.snapshot_path.is_absolute() or not self.report_path.is_absolute():
            raise ValueError("artifact paths must be absolute")
        if self.snapshot_path.name != "snapshot.json" or self.report_path.name != "report.md":
            raise ValueError("artifact names must be snapshot.json and report.md")
        if self.snapshot_path.parent != self.report_path.parent:
            raise ValueError("artifact paths must share one output directory")
        return self


def _record_sort_key(record: SectorRecord) -> tuple[bool, Decimal, int]:
    score = record.relative_rank.score
    return (
        score is None,
        -score if score is not None else Decimal(0),
        _TICKER_POSITION[record.ticker],
    )


def _diagnostic_sort_key(
    diagnostic: PrivateDiagnostic,
) -> tuple[str, str, str]:
    ticker = diagnostic.ticker.value if diagnostic.ticker is not None else ""
    return (diagnostic.issue_code.value, ticker, diagnostic.metric_name or "")


__all__ = [
    "ALL_SECTOR_TICKERS",
    "BENCHMARK_TICKER",
    "FIXED_SECTOR_UNIVERSE",
    "METRIC_QUANTUM",
    "PRIMARY_REGIME_POLICY",
    "RANK_HORIZONS",
    "REGIME_BANDS_BPS",
    "SECTOR_SOURCE_ID",
    "SECTOR_TICKERS",
    "SECTOR_UNIVERSE_VERSION",
    "AxisState",
    "CoverageSummary",
    "DiagnosticIssueCode",
    "MetricMissingReason",
    "MetricValue",
    "NavPoint",
    "NavSeries",
    "ParsedWorkbookSet",
    "PrivateArtifactSet",
    "PrivateDiagnostic",
    "PrivateWorkbookManifest",
    "RankHorizon",
    "RegimePolicy",
    "RegimeResult",
    "RelativeRank",
    "SectorCoverageStatus",
    "SectorDashboardSnapshot",
    "SectorMetricName",
    "SectorMetrics",
    "SectorRecord",
    "SectorRegime",
    "SectorSeriesBundle",
    "SectorTicker",
    "SectorUniverse",
    "WorkbookFailure",
    "WorkbookIssueCode",
]
