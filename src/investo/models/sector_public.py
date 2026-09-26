"""Typed contracts for the limited public IEX-sample sector radar (u145).

These are sibling types to the private u139 NAV contract.  Closed literals and
cross-entity validators make the venue scope, unavailable XLRE identity, and
derived-only boundary impossible to broaden accidentally.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from itertools import pairwise
from types import MappingProxyType
from typing import Annotated, Final, Literal, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_serializer,
    field_validator,
    model_validator,
)

from investo.models.sector import (
    BENCHMARK_TICKER,
    PRIMARY_REGIME_POLICY,
    SECTOR_TICKERS,
    SECTOR_UNIVERSE_VERSION,
    MetricValue,
    RegimePolicy,
    RegimeResult,
    RelativeRank,
    SectorCoverageStatus,
    SectorRegime,
    SectorTicker,
)

PUBLIC_SECTOR_SOURCE_ID: Final[Literal["hf-data-library-iex-daily-v1"]] = (
    "hf-data-library-iex-daily-v1"
)
PUBLIC_SECTOR_PROVIDER: Final[Literal["HF Data Library"]] = "HF Data Library"
PUBLIC_REQUEST_TICKERS: Final[tuple[SectorTicker, ...]] = (
    SectorTicker.SPY,
    SectorTicker.XLB,
    SectorTicker.XLC,
    SectorTicker.XLE,
    SectorTicker.XLF,
    SectorTicker.XLI,
    SectorTicker.XLK,
    SectorTicker.XLP,
    SectorTicker.XLU,
    SectorTicker.XLV,
    SectorTicker.XLY,
)
PUBLIC_SUPPORTED_SECTOR_TICKERS: Final[tuple[SectorTicker, ...]] = tuple(
    ticker for ticker in PUBLIC_REQUEST_TICKERS if ticker is not BENCHMARK_TICKER
)
PUBLIC_STRUCTURALLY_MISSING_TICKERS: Final[tuple[SectorTicker, ...]] = (SectorTicker.XLRE,)
PUBLIC_LICENSE_IDS: Final[tuple[str, ...]] = (
    "hf-data-library-cc-by-4.0",
    "iex-historical-data-terms",
)
_REQUEST_POSITION: Final[dict[SectorTicker, int]] = {
    ticker: position for position, ticker in enumerate(PUBLIC_REQUEST_TICKERS)
}
_SECTOR_POSITION: Final[dict[SectorTicker, int]] = {
    ticker: position for position, ticker in enumerate(SECTOR_TICKERS)
}
_SHA256_PATTERN: Final[str] = r"^sha256:[0-9a-f]{64}$"


class MarketScope(StrEnum):
    """Closed market-scope vocabulary; v1 accepts only the IEX venue sample."""

    IEX_VENUE_SAMPLE = "iex_venue_sample"
    CONSOLIDATED_US_MARKET = "consolidated_us_market"


class PublicAdjustmentPolicy(StrEnum):
    SOURCE_SPLIT_DIVIDEND_ADJUSTED_CLEAN = "source_split_dividend_adjusted_clean"


class PublicSourceIssueCode(StrEnum):
    AUTH_CONFIGURATION = "auth.configuration"
    AUTH_REJECTED = "auth.rejected"
    THROTTLE = "source.throttle"
    TRANSPORT = "source.transport"
    STATUS = "source.status"
    RESPONSE_SIZE = "source.response_size"
    SCHEMA = "source.schema"
    ROW = "source.row"
    CALENDAR = "source.calendar"
    FRESHNESS = "source.freshness"
    INSUFFICIENT_HISTORY = "source.insufficient_history"


class PublicDiagnosticCode(StrEnum):
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    TEMPORARILY_UNAVAILABLE = "temporarily_unavailable"
    INSUFFICIENT_HISTORY = "insufficient_history"
    BENCHMARK_UNAVAILABLE = "benchmark_unavailable"
    METRIC_INSUFFICIENT_HISTORY = "metric.insufficient_history"


class PublicMetricName(StrEnum):
    IEX_PRICE_RETURN_1D = "iex_price_return_1d"
    IEX_PRICE_RETURN_5D = "iex_price_return_5d"
    IEX_PRICE_RETURN_21D = "iex_price_return_21d"
    IEX_PRICE_RETURN_63D = "iex_price_return_63d"
    IEX_PRICE_EXCESS_1D = "iex_price_excess_1d"
    IEX_PRICE_EXCESS_5D = "iex_price_excess_5d"
    IEX_PRICE_EXCESS_21D = "iex_price_excess_21d"
    IEX_PRICE_EXCESS_63D = "iex_price_excess_63d"
    IEX_PRICE_RELATIVE_ACCELERATION_5D = "iex_price_relative_acceleration_5d"
    IEX_PRICE_REALIZED_VOLATILITY_20D = "iex_price_realized_volatility_20d"
    IEX_PRICE_MAX_DRAWDOWN_20D = "iex_price_max_drawdown_20d"


class SectorAvailability(StrEnum):
    AVAILABLE = "available"
    TEMPORARILY_UNAVAILABLE = "temporarily_unavailable"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    INSUFFICIENT_HISTORY = "insufficient_history"


class FreshnessState(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    UNKNOWN = "unknown"


class PublicSectorBuildStatus(StrEnum):
    PROMOTED = "promoted"
    UNCHANGED = "unchanged"
    HELD_LAST_GOOD = "held_last_good"
    BLOCKED = "blocked"


def _require_https(value: HttpUrl) -> HttpUrl:
    if value.scheme != "https":
        raise ValueError("attribution URL must use HTTPS")
    return value


HttpsUrl = Annotated[HttpUrl, AfterValidator(_require_https)]
PublicFailureCode = PublicSourceIssueCode | PublicDiagnosticCode


def _date_only(value: object) -> date:
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


class PublicBarPoint(BaseModel):
    """One validated IEX row retained in the bounded calculation window."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    trading_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int = Field(ge=0)
    source: Literal["iex"] = "iex"

    @field_validator("trading_date", mode="before")
    @classmethod
    def _validate_date(cls, value: object) -> date:
        return _date_only(value)

    @field_validator("open", "high", "low", "close", mode="before")
    @classmethod
    def _reject_boolean_price(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("OHLC values must be numeric, not boolean")
        return value

    @field_validator("open", "high", "low", "close")
    @classmethod
    def _validate_price(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value <= 0:
            raise ValueError("OHLC values must be finite and strictly positive")
        return value

    @field_validator("volume", mode="before")
    @classmethod
    def _reject_boolean_volume(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("volume must be an integer, not boolean")
        return value

    @model_validator(mode="after")
    def _validate_bounds(self) -> Self:
        if self.low > min(self.open, self.close) or self.high < max(self.open, self.close):
            raise ValueError("OHLC bounds must satisfy low <= open/close <= high")
        if self.low > self.high:
            raise ValueError("OHLC low must not exceed high")
        return self


class PublicBarSeries(BaseModel):
    """One strictly ascending series of retained IEX daily bars."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ticker: SectorTicker
    points: tuple[PublicBarPoint, ...] = Field(min_length=2, max_length=10_000)
    first_date: date
    latest_date: date
    market_scope: Literal[MarketScope.IEX_VENUE_SAMPLE] = MarketScope.IEX_VENUE_SAMPLE
    adjustment: Literal[PublicAdjustmentPolicy.SOURCE_SPLIT_DIVIDEND_ADJUSTED_CLEAN] = (
        PublicAdjustmentPolicy.SOURCE_SPLIT_DIVIDEND_ADJUSTED_CLEAN
    )

    @model_validator(mode="after")
    def _validate_series(self) -> Self:
        if self.ticker not in PUBLIC_REQUEST_TICKERS:
            raise ValueError("public bar ticker must belong to the fixed HF request set")
        dates = tuple(point.trading_date for point in self.points)
        if any(current >= following for current, following in pairwise(dates)):
            raise ValueError("public bar points must be strictly ascending with unique dates")
        if self.first_date != dates[0] or self.latest_date != dates[-1]:
            raise ValueError("first_date/latest_date must equal point endpoints")
        return self


class PublicSourceFailure(BaseModel):
    """Ticker-scoped provider failure with no provider-controlled text."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ticker: SectorTicker
    issue_code: PublicSourceIssueCode
    retryable: bool

    @model_validator(mode="after")
    def _validate_requested_ticker(self) -> Self:
        if self.ticker not in PUBLIC_REQUEST_TICKERS:
            raise ValueError("source failures can reference only requested HF tickers")
        return self


class PublicParsedSet(BaseModel):
    """Exactly one success or closed failure per fixed HF request identity."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    benchmark: PublicBarSeries | None = None
    sectors: Mapping[SectorTicker, PublicBarSeries] = Field(default_factory=dict)
    failures: tuple[PublicSourceFailure, ...] = ()

    @field_validator("sectors")
    @classmethod
    def _normalize_sectors(
        cls, value: Mapping[SectorTicker, PublicBarSeries]
    ) -> Mapping[SectorTicker, PublicBarSeries]:
        for ticker, series in value.items():
            if ticker not in PUBLIC_SUPPORTED_SECTOR_TICKERS or series.ticker is not ticker:
                raise ValueError("sector mapping must use matching supported HF sector tickers")
        return MappingProxyType(
            {ticker: value[ticker] for ticker in PUBLIC_SUPPORTED_SECTOR_TICKERS if ticker in value}
        )

    @field_serializer("sectors")
    def _serialize_sectors(
        self, value: Mapping[SectorTicker, PublicBarSeries]
    ) -> dict[SectorTicker, PublicBarSeries]:
        return dict(value)

    @field_validator("failures")
    @classmethod
    def _normalize_failures(
        cls, value: tuple[PublicSourceFailure, ...]
    ) -> tuple[PublicSourceFailure, ...]:
        if len({failure.ticker for failure in value}) != len(value):
            raise ValueError("source failures must contain unique tickers")
        return tuple(sorted(value, key=lambda failure: _REQUEST_POSITION[failure.ticker]))

    @model_validator(mode="after")
    def _validate_identity_partition(self) -> Self:
        if self.benchmark is not None and self.benchmark.ticker is not BENCHMARK_TICKER:
            raise ValueError("public benchmark must be SPY")
        successes = set(self.sectors)
        if self.benchmark is not None:
            successes.add(BENCHMARK_TICKER)
        failures = {failure.ticker for failure in self.failures}
        if successes & failures:
            raise ValueError("ticker cannot be both public source success and failure")
        if successes | failures != set(PUBLIC_REQUEST_TICKERS):
            raise ValueError("parsed set must account for every fixed HF request ticker")
        return self


class ValuePoint(BaseModel):
    """Source-neutral positive observation passed only to mathematical kernels."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    trading_date: date
    value: Decimal

    @field_validator("trading_date", mode="before")
    @classmethod
    def _validate_date(cls, value: object) -> date:
        return _date_only(value)

    @field_validator("value", mode="before")
    @classmethod
    def _reject_boolean_value(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("value must be numeric, not boolean")
        return value

    @field_validator("value")
    @classmethod
    def _validate_value(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value <= 0:
            raise ValueError("value must be finite and strictly positive")
        return value


class ValueSeries(BaseModel):
    """Strictly ascending source-neutral series with stable identity."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ticker: SectorTicker
    points: tuple[ValuePoint, ...] = Field(min_length=2, max_length=10_000)

    @model_validator(mode="after")
    def _validate_series(self) -> Self:
        dates = tuple(point.trading_date for point in self.points)
        if any(current >= following for current, following in pairwise(dates)):
            raise ValueError("value points must be strictly ascending with unique dates")
        return self

    @property
    def first_date(self) -> date:
        return self.points[0].trading_date

    @property
    def latest_date(self) -> date:
        return self.points[-1].trading_date


class PublicCoverageSummary(BaseModel):
    """u145 coverage thresholds without changing u139's private contract.

    The public product needs 64 observations for its 63-session fields, while
    u139's stable ``CoverageSummary`` moves out of warming-up at 22 rows.  A
    sibling type preserves both truths and keeps public reason codes public.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: SectorCoverageStatus
    available_sector_count: int = Field(ge=0, le=11)
    expected_sector_count: Literal[11] = 11
    benchmark_available: bool
    common_as_of: date | None = None
    benchmark_observation_count: int = Field(ge=0)
    missing_tickers: tuple[SectorTicker, ...] = ()
    reason_codes: tuple[PublicDiagnosticCode, ...] = ()

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
        cls, value: tuple[PublicDiagnosticCode, ...]
    ) -> tuple[PublicDiagnosticCode, ...]:
        return tuple(sorted(set(value), key=str))

    @model_validator(mode="after")
    def _validate_coverage(self) -> Self:
        if self.available_sector_count + len(self.missing_tickers) != 11:
            raise ValueError("available and missing public sector counts must total eleven")
        if not self.benchmark_available and self.benchmark_observation_count != 0:
            raise ValueError("unavailable public benchmark must have zero observations")
        if self.status is SectorCoverageStatus.NORMAL:
            if not (
                self.benchmark_available
                and self.common_as_of is not None
                and self.available_sector_count == 11
                and self.benchmark_observation_count >= 64
            ):
                raise ValueError("normal public coverage requires SPY, 11 sectors, and 64 rows")
        elif self.status is SectorCoverageStatus.PARTIAL:
            if not (
                self.benchmark_available
                and self.common_as_of is not None
                and 8 <= self.available_sector_count <= 10
                and self.benchmark_observation_count >= 64
            ):
                raise ValueError("partial public coverage requires SPY, 8-10 sectors, and 64 rows")
        elif self.status is SectorCoverageStatus.WARMING_UP and not (
            self.benchmark_available
            and self.common_as_of is not None
            and self.available_sector_count >= 8
            and 6 <= self.benchmark_observation_count <= 63
        ):
            raise ValueError("warming_up public coverage requires SPY, 8 sectors, and 6-63 rows")
        return self


class AttributionEntry(BaseModel):
    """One mandatory, HTTPS-only public attribution entry."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    attribution_id: Literal["hf-data-library-cc-by-4.0", "iex-historical-data"]
    display_text: str = Field(min_length=1, max_length=320)
    url: HttpsUrl
    required: Literal[True] = True


HF_DATA_LIBRARY_ATTRIBUTION: Final[AttributionEntry] = AttributionEntry(
    attribution_id="hf-data-library-cc-by-4.0",
    display_text=(
        "Data from the HF Data Library (Elkassabgi 2026), available at "
        "https://hfdatalibrary.com under CC BY 4.0."
    ),
    url="https://hfdatalibrary.com/pages/license",
)
IEX_HISTORICAL_DATA_ATTRIBUTION: Final[AttributionEntry] = AttributionEntry(
    attribution_id="iex-historical-data",
    display_text=(
        "Data provided for free by IEX. By accessing or using IEX Historical Data, "
        "you agree to the IEX Historical Data Terms of Use."
    ),
    url="https://www.iex.io/legal/hist-data-terms",
)
REQUIRED_PUBLIC_ATTRIBUTIONS: Final[tuple[AttributionEntry, ...]] = (
    HF_DATA_LIBRARY_ATTRIBUTION,
    IEX_HISTORICAL_DATA_ATTRIBUTION,
)


class PublicSourceProvenance(BaseModel):
    """Canonical source, scope, rights, and date identity for one snapshot."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_id: Literal["hf-data-library-iex-daily-v1"] = PUBLIC_SECTOR_SOURCE_ID
    provider: Literal["HF Data Library"] = PUBLIC_SECTOR_PROVIDER
    market_scope: Literal[MarketScope.IEX_VENUE_SAMPLE] = MarketScope.IEX_VENUE_SAMPLE
    requested_tickers: tuple[SectorTicker, ...] = PUBLIC_REQUEST_TICKERS
    supported_tickers: tuple[SectorTicker, ...] = PUBLIC_REQUEST_TICKERS
    missing_tickers: tuple[SectorTicker, ...] = PUBLIC_STRUCTURALLY_MISSING_TICKERS
    adjustment: Literal[PublicAdjustmentPolicy.SOURCE_SPLIT_DIVIDEND_ADJUSTED_CLEAN] = (
        PublicAdjustmentPolicy.SOURCE_SPLIT_DIVIDEND_ADJUSTED_CLEAN
    )
    transport: Literal["signed_daily_parquet_v1"] = "signed_daily_parquet_v1"
    data_version: Literal["clean"] = "clean"
    target_date: date
    as_of_date: date | None = None
    license_ids: tuple[str, ...] = PUBLIC_LICENSE_IDS
    attributions: tuple[AttributionEntry, ...] = REQUIRED_PUBLIC_ATTRIBUTIONS
    schema_version: Literal[1] = 1

    @model_validator(mode="after")
    def _validate_closed_provenance(self) -> Self:
        if self.requested_tickers != PUBLIC_REQUEST_TICKERS:
            raise ValueError("requested_tickers must equal the fixed HF request set")
        if self.supported_tickers != PUBLIC_REQUEST_TICKERS:
            raise ValueError("supported_tickers must equal the qualified HF v1 set")
        if self.missing_tickers != PUBLIC_STRUCTURALLY_MISSING_TICKERS:
            raise ValueError("XLRE must be the sole structurally missing HF v1 ticker")
        if self.license_ids != PUBLIC_LICENSE_IDS:
            raise ValueError("license_ids must equal the fixed HF/IEX rights set")
        if self.attributions != REQUIRED_PUBLIC_ATTRIBUTIONS:
            raise ValueError("attributions must equal the fixed HF/IEX entries in display order")
        if self.as_of_date is not None and self.as_of_date > self.target_date:
            raise ValueError("source as-of date must not be after target date")
        return self


class PublicSectorSeriesBundle(BaseModel):
    """Derived close-only public input bundle; contains no OHLCV arrays."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[1] = 1
    source_id: Literal["hf-data-library-iex-daily-v1"] = PUBLIC_SECTOR_SOURCE_ID
    market_scope: Literal[MarketScope.IEX_VENUE_SAMPLE] = MarketScope.IEX_VENUE_SAMPLE
    as_of_date: date | None = None
    benchmark: ValueSeries | None = None
    sectors: tuple[ValueSeries, ...] = ()
    coverage: PublicCoverageSummary
    failures: tuple[PublicSourceFailure, ...] = ()
    provenance: PublicSourceProvenance

    @field_validator("sectors")
    @classmethod
    def _normalize_sectors(cls, value: tuple[ValueSeries, ...]) -> tuple[ValueSeries, ...]:
        if any(
            series.ticker is BENCHMARK_TICKER
            or series.ticker not in PUBLIC_SUPPORTED_SECTOR_TICKERS
            for series in value
        ):
            raise ValueError("public bundle sectors must use supported non-SPY tickers")
        if len({series.ticker for series in value}) != len(value):
            raise ValueError("public bundle sector series must contain unique tickers")
        return tuple(sorted(value, key=lambda series: _SECTOR_POSITION[series.ticker]))

    @field_validator("failures")
    @classmethod
    def _normalize_failures(
        cls, value: tuple[PublicSourceFailure, ...]
    ) -> tuple[PublicSourceFailure, ...]:
        if len({failure.ticker for failure in value}) != len(value):
            raise ValueError("public bundle failures must contain unique tickers")
        return tuple(sorted(value, key=lambda failure: _REQUEST_POSITION[failure.ticker]))

    @model_validator(mode="after")
    def _validate_bundle(self) -> Self:
        if self.benchmark is not None and self.benchmark.ticker is not BENCHMARK_TICKER:
            raise ValueError("public bundle benchmark must be SPY")
        if self.coverage.benchmark_available != (self.benchmark is not None):
            raise ValueError("coverage benchmark flag must match public benchmark series")
        benchmark_count = len(self.benchmark.points) if self.benchmark is not None else 0
        if self.coverage.benchmark_observation_count != benchmark_count:
            raise ValueError("coverage benchmark count must match public benchmark series")
        if self.coverage.available_sector_count != len(self.sectors):
            raise ValueError("coverage count must match public sector series")
        available = {series.ticker for series in self.sectors}
        if set(self.coverage.missing_tickers) != set(SECTOR_TICKERS) - available:
            raise ValueError("coverage missing_tickers must complement public sector series")
        if SectorTicker.XLRE in available:
            raise ValueError("XLRE cannot have a series under the HF v1 source")
        if self.as_of_date != self.coverage.common_as_of:
            raise ValueError("bundle as_of_date must equal coverage common_as_of")
        if self.as_of_date != self.provenance.as_of_date:
            raise ValueError("bundle and provenance as-of dates must match")
        if self.as_of_date is not None:
            series = (*self.sectors, *((self.benchmark,) if self.benchmark is not None else ()))
            if any(item.latest_date != self.as_of_date for item in series):
                raise ValueError("all metric-bearing public series must share the as-of date")
        successes = available | ({BENCHMARK_TICKER} if self.benchmark is not None else set())
        failures = {failure.ticker for failure in self.failures}
        if successes & failures:
            raise ValueError("ticker cannot be both public bundle success and failure")
        if successes | failures != set(PUBLIC_REQUEST_TICKERS):
            raise ValueError("public bundle must account for every fixed HF request ticker")
        return self


class PublicSectorMetrics(BaseModel):
    """All IEX-price metric slots for one fixed sector identity."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ticker: SectorTicker
    iex_price_return_1d: MetricValue
    iex_price_return_5d: MetricValue
    iex_price_return_21d: MetricValue
    iex_price_return_63d: MetricValue
    iex_price_excess_1d: MetricValue
    iex_price_excess_5d: MetricValue
    iex_price_excess_21d: MetricValue
    iex_price_excess_63d: MetricValue
    iex_price_relative_acceleration_5d: MetricValue
    iex_price_realized_volatility_20d: MetricValue
    iex_price_max_drawdown_20d: MetricValue

    @model_validator(mode="after")
    def _validate_ticker(self) -> Self:
        if self.ticker is BENCHMARK_TICKER:
            raise ValueError("public sector metrics cannot use SPY")
        return self


_ALL_PUBLIC_METRIC_FIELDS: Final[tuple[PublicMetricName, ...]] = tuple(PublicMetricName)
_WARMING_SUPPRESSED_PUBLIC_METRICS: Final[tuple[PublicMetricName, ...]] = (
    PublicMetricName.IEX_PRICE_RETURN_21D,
    PublicMetricName.IEX_PRICE_RETURN_63D,
    PublicMetricName.IEX_PRICE_EXCESS_21D,
    PublicMetricName.IEX_PRICE_EXCESS_63D,
    PublicMetricName.IEX_PRICE_RELATIVE_ACCELERATION_5D,
    PublicMetricName.IEX_PRICE_REALIZED_VOLATILITY_20D,
    PublicMetricName.IEX_PRICE_MAX_DRAWDOWN_20D,
)


class PublicSectorRecord(BaseModel):
    """One sector's public availability, metrics, regime, rank, and diagnostics."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ticker: SectorTicker
    availability: SectorAvailability
    metrics: PublicSectorMetrics
    primary_regime: RegimeResult
    relative_rank: RelativeRank
    diagnostic_codes: tuple[PublicDiagnosticCode, ...] = ()

    @field_validator("diagnostic_codes")
    @classmethod
    def _normalize_diagnostics(
        cls, value: tuple[PublicDiagnosticCode, ...]
    ) -> tuple[PublicDiagnosticCode, ...]:
        return tuple(sorted(set(value), key=str))

    @model_validator(mode="after")
    def _validate_record(self) -> Self:
        if self.ticker is BENCHMARK_TICKER:
            raise ValueError("public sector records cannot use SPY")
        if self.metrics.ticker is not self.ticker or self.primary_regime.ticker is not self.ticker:
            raise ValueError("nested ticker identities must match the public sector record")
        if self.primary_regime.policy_id != PRIMARY_REGIME_POLICY.policy_id:
            raise ValueError("public primary regime must use sector-regime-v1")
        if self.availability in {
            SectorAvailability.TEMPORARILY_UNAVAILABLE,
            SectorAvailability.PROVIDER_UNAVAILABLE,
            SectorAvailability.INSUFFICIENT_HISTORY,
        }:
            _require_suppressed_record(self)
        if self.ticker is SectorTicker.XLRE:
            if self.availability is not SectorAvailability.PROVIDER_UNAVAILABLE:
                raise ValueError("XLRE must always be provider_unavailable under HF v1")
            if PublicDiagnosticCode.PROVIDER_UNAVAILABLE not in self.diagnostic_codes:
                raise ValueError("XLRE must expose the provider_unavailable diagnostic")
        return self


class PublicSectorDashboardSnapshot(BaseModel):
    """Immutable, derived-only machine snapshot for the limited public radar."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[1] = 1
    snapshot_id: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    universe_version: Literal["select-sector-spdr-v1"] = SECTOR_UNIVERSE_VERSION
    input_kind: Literal["iex_daily_close"] = "iex_daily_close"
    source_id: Literal["hf-data-library-iex-daily-v1"] = PUBLIC_SECTOR_SOURCE_ID
    market_scope: Literal[MarketScope.IEX_VENUE_SAMPLE] = MarketScope.IEX_VENUE_SAMPLE
    actual_market_ohlcv: Literal[True] = True
    consolidated_market_data: Literal[False] = False
    as_of_date: date | None = None
    freshness: FreshnessState
    coverage: PublicCoverageSummary
    records: tuple[PublicSectorRecord, ...]
    primary_policy: RegimePolicy = PRIMARY_REGIME_POLICY
    provenance: PublicSourceProvenance

    @field_validator("records")
    @classmethod
    def _normalize_records(
        cls, value: tuple[PublicSectorRecord, ...]
    ) -> tuple[PublicSectorRecord, ...]:
        if len(value) != 11 or {record.ticker for record in value} != set(SECTOR_TICKERS):
            raise ValueError("public snapshot must contain exactly eleven sector records")
        return tuple(sorted(value, key=lambda record: _SECTOR_POSITION[record.ticker]))

    @model_validator(mode="after")
    def _validate_snapshot(self) -> Self:
        if (
            self.freshness is not FreshnessState.FRESH
            and self.coverage.status is not SectorCoverageStatus.INSUFFICIENT
        ):
            raise ValueError("non-fresh public snapshots require insufficient coverage")
        if self.as_of_date != self.coverage.common_as_of:
            raise ValueError("snapshot as_of_date must equal coverage common_as_of")
        if self.as_of_date != self.provenance.as_of_date:
            raise ValueError("snapshot and provenance as-of dates must match")
        if self.primary_policy != PRIMARY_REGIME_POLICY:
            raise ValueError("snapshot primary policy must be sector-regime-v1 at 10 bps")

        unavailable = {
            record.ticker
            for record in self.records
            if record.availability
            in {
                SectorAvailability.TEMPORARILY_UNAVAILABLE,
                SectorAvailability.PROVIDER_UNAVAILABLE,
                SectorAvailability.INSUFFICIENT_HISTORY,
            }
        }
        if unavailable != set(self.coverage.missing_tickers):
            raise ValueError("record availability must match coverage missing_tickers")
        if self.coverage.available_sector_count != 11 - len(unavailable):
            raise ValueError("record availability must match coverage available count")

        xlre = next(record for record in self.records if record.ticker is SectorTicker.XLRE)
        _require_suppressed_record(xlre)
        if self.coverage.status is SectorCoverageStatus.INSUFFICIENT:
            for record in self.records:
                _require_suppressed_record(record)
        elif self.coverage.status is SectorCoverageStatus.WARMING_UP:
            for record in self.records:
                if any(
                    getattr(record.metrics, metric_name.value).value is not None
                    for metric_name in _WARMING_SUPPRESSED_PUBLIC_METRICS
                ):
                    raise ValueError("warming_up snapshots may expose only 1D/5D public metrics")
                if (
                    record.primary_regime.regime is not SectorRegime.INSUFFICIENT
                    or record.relative_rank.score is not None
                ):
                    raise ValueError("warming_up snapshots must suppress public regime and rank")
        else:
            for record in self.records:
                if record.ticker in unavailable:
                    continue
                if record.availability is not SectorAvailability.AVAILABLE:
                    raise ValueError("metric-bearing public records must be available")
                if any(
                    getattr(record.metrics, metric_name.value).value is None
                    for metric_name in _ALL_PUBLIC_METRIC_FIELDS
                ):
                    raise ValueError("partial/normal public records require every metric value")
                if (
                    record.primary_regime.regime is SectorRegime.INSUFFICIENT
                    or record.relative_rank.score is None
                ):
                    raise ValueError("partial/normal public records require regime and rank")
        return self


class RenderedPublicSectorProjection(BaseModel):
    """Validated deterministic JSON/Markdown byte pair for one snapshot id."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    snapshot_bytes: bytes = Field(min_length=1)
    markdown_bytes: bytes = Field(min_length=1)
    snapshot_id: str = Field(pattern=_SHA256_PATTERN)

    @model_validator(mode="after")
    def _validate_pair(self) -> Self:
        for payload in (self.snapshot_bytes, self.markdown_bytes):
            try:
                payload.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError("public projection bytes must be UTF-8") from exc
            if not payload.endswith(b"\n"):
                raise ValueError("public projection bytes must be newline-terminated")
            if self.snapshot_id.encode("ascii") not in payload:
                raise ValueError("both public projections must contain the snapshot id")
        return self


class PublicSectorBuildOutcome(BaseModel):
    """Closed promotion/hold/block result with honest failure signaling."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: PublicSectorBuildStatus
    snapshot_id: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    as_of_date: date | None = None
    failure_codes: tuple[PublicFailureCode, ...] = ()

    @field_validator("failure_codes")
    @classmethod
    def _normalize_failure_codes(
        cls, value: tuple[PublicFailureCode, ...]
    ) -> tuple[PublicFailureCode, ...]:
        return tuple(sorted(set(value), key=str))

    @model_validator(mode="after")
    def _validate_outcome(self) -> Self:
        if self.status in {
            PublicSectorBuildStatus.PROMOTED,
            PublicSectorBuildStatus.UNCHANGED,
        }:
            if self.snapshot_id is None or self.as_of_date is None or self.failure_codes:
                raise ValueError("successful outcomes require identity/date and no failures")
        elif self.status is PublicSectorBuildStatus.HELD_LAST_GOOD:
            if self.snapshot_id is None or self.as_of_date is None or not self.failure_codes:
                raise ValueError("held_last_good requires prior identity/date and failures")
        elif self.snapshot_id is not None or self.as_of_date is not None or not self.failure_codes:
            raise ValueError("blocked requires failures and no snapshot identity/date")
        return self


def _require_suppressed_record(record: PublicSectorRecord) -> None:
    if any(
        getattr(record.metrics, metric_name.value).value is not None
        for metric_name in _ALL_PUBLIC_METRIC_FIELDS
    ):
        raise ValueError("unavailable public sectors must suppress every metric value")
    if (
        record.primary_regime.regime is not SectorRegime.INSUFFICIENT
        or record.relative_rank.score is not None
    ):
        raise ValueError("unavailable public sectors must suppress regime and rank")


__all__ = [
    "HF_DATA_LIBRARY_ATTRIBUTION",
    "IEX_HISTORICAL_DATA_ATTRIBUTION",
    "PUBLIC_LICENSE_IDS",
    "PUBLIC_REQUEST_TICKERS",
    "PUBLIC_SECTOR_PROVIDER",
    "PUBLIC_SECTOR_SOURCE_ID",
    "PUBLIC_STRUCTURALLY_MISSING_TICKERS",
    "PUBLIC_SUPPORTED_SECTOR_TICKERS",
    "REQUIRED_PUBLIC_ATTRIBUTIONS",
    "AttributionEntry",
    "FreshnessState",
    "HttpsUrl",
    "MarketScope",
    "PublicAdjustmentPolicy",
    "PublicBarPoint",
    "PublicBarSeries",
    "PublicCoverageSummary",
    "PublicDiagnosticCode",
    "PublicFailureCode",
    "PublicMetricName",
    "PublicParsedSet",
    "PublicSectorBuildOutcome",
    "PublicSectorBuildStatus",
    "PublicSectorDashboardSnapshot",
    "PublicSectorMetrics",
    "PublicSectorRecord",
    "PublicSectorSeriesBundle",
    "PublicSourceFailure",
    "PublicSourceIssueCode",
    "PublicSourceProvenance",
    "RenderedPublicSectorProjection",
    "SectorAvailability",
    "ValuePoint",
    "ValueSeries",
]
