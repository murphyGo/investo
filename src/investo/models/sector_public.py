"""Typed contracts for the Yahoo daily-price public sector radar (u145).

These are sibling types to the private u139 NAV contract.  Closed literals and
cross-entity validators make the provider scope, fixed ETF/equity identities, and
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
    SerializerFunctionWrapHandler,
    field_serializer,
    field_validator,
    model_serializer,
    model_validator,
)

from investo.models.market_groups import (
    ADDITIONAL_REQUEST_TICKERS,
    GROUP_BY_ID,
    MARKET_GROUP_IDS,
    AdditionalAssetTicker,
    GroupCategory,
    GroupKind,
    MarketGroupId,
    PublicAssetTicker,
)
from investo.models.sector import (
    BENCHMARK_TICKER,
    PRIMARY_REGIME_POLICY,
    SECTOR_TICKERS,
    SECTOR_UNIVERSE_VERSION,
    AxisState,
    MetricMissingReason,
    MetricValue,
    RankHorizon,
    RegimePolicy,
    RegimeResult,
    RelativeRank,
    SectorCoverageStatus,
    SectorRegime,
    SectorTicker,
)

PUBLIC_SECTOR_SOURCE_ID: Final[Literal["yahoo-chart-daily-v2"]] = "yahoo-chart-daily-v2"
PUBLIC_SECTOR_PROVIDER: Final[Literal["Yahoo Finance"]] = "Yahoo Finance"
PUBLIC_REQUEST_TICKERS: Final[tuple[SectorTicker, ...]] = (
    SectorTicker.SPY,
    SectorTicker.XLB,
    SectorTicker.XLC,
    SectorTicker.XLE,
    SectorTicker.XLF,
    SectorTicker.XLI,
    SectorTicker.XLK,
    SectorTicker.XLP,
    SectorTicker.XLRE,
    SectorTicker.XLU,
    SectorTicker.XLV,
    SectorTicker.XLY,
)
PUBLIC_SUPPORTED_SECTOR_TICKERS: Final[tuple[SectorTicker, ...]] = tuple(
    ticker for ticker in PUBLIC_REQUEST_TICKERS if ticker is not BENCHMARK_TICKER
)
PUBLIC_STRUCTURALLY_MISSING_TICKERS: Final[tuple[SectorTicker, ...]] = ()
PUBLIC_LICENSE_IDS: Final[tuple[str, ...]] = ()
_REQUEST_POSITION: Final[dict[SectorTicker, int]] = {
    ticker: position for position, ticker in enumerate(PUBLIC_REQUEST_TICKERS)
}
_SECTOR_POSITION: Final[dict[SectorTicker, int]] = {
    ticker: position for position, ticker in enumerate(SECTOR_TICKERS)
}
_SHA256_PATTERN: Final[str] = r"^sha256:[0-9a-f]{64}$"


class MarketScope(StrEnum):
    """Closed market-scope vocabulary; v2 identifies provider-reported US ETF prices."""

    PROVIDER_REPORTED_US_EQUITY = "provider_reported_us_equity"
    CONSOLIDATED_US_MARKET = "consolidated_us_market"


class PublicAdjustmentPolicy(StrEnum):
    PROVIDER_CLOSE = "provider_close_not_total_return"


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
    PRICE_RETURN_1D = "price_return_1d"
    PRICE_RETURN_5D = "price_return_5d"
    PRICE_RETURN_21D = "price_return_21d"
    PRICE_RETURN_63D = "price_return_63d"
    PRICE_EXCESS_1D = "price_excess_1d"
    PRICE_EXCESS_5D = "price_excess_5d"
    PRICE_EXCESS_21D = "price_excess_21d"
    PRICE_EXCESS_63D = "price_excess_63d"
    PRICE_RELATIVE_ACCELERATION_5D = "price_relative_acceleration_5d"
    PRICE_REALIZED_VOLATILITY_20D = "price_realized_volatility_20d"
    PRICE_MAX_DRAWDOWN_20D = "price_max_drawdown_20d"


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


class PublicBuildIssueCode(StrEnum):
    RESOURCE = "build.resource"
    PROJECTION = "build.projection"
    STORE = "build.store"
    INTERNAL = "build.internal"


def _require_https(value: HttpUrl) -> HttpUrl:
    if value.scheme != "https":
        raise ValueError("attribution URL must use HTTPS")
    return value


HttpsUrl = Annotated[HttpUrl, AfterValidator(_require_https)]
PublicFailureCode = PublicSourceIssueCode | PublicDiagnosticCode | PublicBuildIssueCode


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
    """One validated Yahoo row retained in the bounded calculation window."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    trading_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int = Field(ge=0)
    source: Literal["yahoo"] = "yahoo"

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
    """One strictly ascending series of retained Yahoo daily bars."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ticker: PublicAssetTicker
    points: tuple[PublicBarPoint, ...] = Field(min_length=2, max_length=256)
    first_date: date
    latest_date: date
    market_scope: Literal[MarketScope.PROVIDER_REPORTED_US_EQUITY] = (
        MarketScope.PROVIDER_REPORTED_US_EQUITY
    )
    adjustment: Literal[PublicAdjustmentPolicy.PROVIDER_CLOSE] = (
        PublicAdjustmentPolicy.PROVIDER_CLOSE
    )

    @model_validator(mode="after")
    def _validate_series(self) -> Self:
        if self.ticker not in (*PUBLIC_REQUEST_TICKERS, *ADDITIONAL_REQUEST_TICKERS):
            raise ValueError("public bar ticker must belong to the fixed Yahoo request set")
        dates = tuple(point.trading_date for point in self.points)
        if any(current >= following for current, following in pairwise(dates)):
            raise ValueError("public bar points must be strictly ascending with unique dates")
        if self.first_date != dates[0] or self.latest_date != dates[-1]:
            raise ValueError("first_date/latest_date must equal point endpoints")
        return self


class PublicSourceFailure(BaseModel):
    """Ticker-scoped provider failure with no provider-controlled text."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ticker: PublicAssetTicker
    issue_code: PublicSourceIssueCode
    retryable: bool

    @model_validator(mode="after")
    def _validate_requested_ticker(self) -> Self:
        if self.ticker not in (*PUBLIC_REQUEST_TICKERS, *ADDITIONAL_REQUEST_TICKERS):
            raise ValueError("source failures can reference only requested Yahoo tickers")
        return self


class AdditionalParsedSet(BaseModel):
    """Exactly one validated outcome for each fixed additional asset."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    assets: Mapping[AdditionalAssetTicker, PublicBarSeries] = Field(default_factory=dict)
    failures: tuple[PublicSourceFailure, ...] = ()

    @field_validator("assets")
    @classmethod
    def _normalize_assets(
        cls, value: Mapping[AdditionalAssetTicker, PublicBarSeries]
    ) -> Mapping[AdditionalAssetTicker, PublicBarSeries]:
        if any(series.ticker is not ticker for ticker, series in value.items()):
            raise ValueError("additional asset identities must match")
        return MappingProxyType(
            {ticker: value[ticker] for ticker in ADDITIONAL_REQUEST_TICKERS if ticker in value}
        )

    @field_serializer("assets")
    def _serialize_assets(
        self, value: Mapping[AdditionalAssetTicker, PublicBarSeries]
    ) -> dict[AdditionalAssetTicker, PublicBarSeries]:
        return dict(value)

    @model_validator(mode="after")
    def _validate_partition(self) -> Self:
        failures = {failure.ticker for failure in self.failures}
        if len(failures) != len(self.failures) or set(self.assets) & failures:
            raise ValueError("additional outcomes must be unique and disjoint")
        if set(self.assets) | failures != set(ADDITIONAL_REQUEST_TICKERS):
            raise ValueError("additional outcomes must account for every fixed asset")
        return self


class PublicParsedSet(BaseModel):
    """Exactly one success or closed failure per fixed Yahoo request identity."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    benchmark: PublicBarSeries | None = None
    sectors: Mapping[SectorTicker, PublicBarSeries] = Field(default_factory=dict)
    failures: tuple[PublicSourceFailure, ...] = ()
    additional: AdditionalParsedSet | None = None

    @field_validator("sectors")
    @classmethod
    def _normalize_sectors(
        cls, value: Mapping[SectorTicker, PublicBarSeries]
    ) -> Mapping[SectorTicker, PublicBarSeries]:
        for ticker, series in value.items():
            if ticker not in PUBLIC_SUPPORTED_SECTOR_TICKERS or series.ticker is not ticker:
                raise ValueError("sector mapping must use matching supported Yahoo sector tickers")
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
        if any(failure.ticker not in PUBLIC_REQUEST_TICKERS for failure in value):
            raise ValueError("overview failures must use overview identities")
        if len({failure.ticker for failure in value}) != len(value):
            raise ValueError("source failures must contain unique tickers")
        return tuple(
            sorted(value, key=lambda failure: PUBLIC_REQUEST_TICKERS.index(failure.ticker))
        )

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
            raise ValueError("parsed set must account for every fixed Yahoo request ticker")
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
    points: tuple[ValuePoint, ...] = Field(min_length=2, max_length=256)

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

    attribution_id: Literal["yahoo-finance"]
    display_text: str = Field(min_length=1, max_length=320)
    url: HttpsUrl
    required: Literal[True] = True


YAHOO_FINANCE_ATTRIBUTION: Final[AttributionEntry] = AttributionEntry(
    attribution_id="yahoo-finance",
    display_text="Yahoo Finance — daily ETF price data",
    url="https://finance.yahoo.com/",
)
REQUIRED_PUBLIC_ATTRIBUTIONS: Final[tuple[AttributionEntry, ...]] = (YAHOO_FINANCE_ATTRIBUTION,)
MARKET_GROUP_REQUEST_TICKERS: Final = (*PUBLIC_REQUEST_TICKERS, *ADDITIONAL_REQUEST_TICKERS)
MARKET_GROUP_ATTRIBUTIONS: Final[tuple[AttributionEntry, ...]] = (
    AttributionEntry(
        attribution_id="yahoo-finance",
        display_text="Yahoo Finance — daily ETF and equity price data",
        url="https://finance.yahoo.com/",
    ),
)


class PublicSourceProvenance(BaseModel):
    """Canonical source, scope, rights, and date identity for one snapshot."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_id: Literal["yahoo-chart-daily-v2"] = PUBLIC_SECTOR_SOURCE_ID
    provider: Literal["Yahoo Finance"] = PUBLIC_SECTOR_PROVIDER
    market_scope: Literal[MarketScope.PROVIDER_REPORTED_US_EQUITY] = (
        MarketScope.PROVIDER_REPORTED_US_EQUITY
    )
    requested_tickers: tuple[PublicAssetTicker, ...] = PUBLIC_REQUEST_TICKERS
    supported_tickers: tuple[PublicAssetTicker, ...] = PUBLIC_REQUEST_TICKERS
    missing_tickers: tuple[SectorTicker, ...] = PUBLIC_STRUCTURALLY_MISSING_TICKERS
    adjustment: Literal[PublicAdjustmentPolicy.PROVIDER_CLOSE] = (
        PublicAdjustmentPolicy.PROVIDER_CLOSE
    )
    transport: Literal["yahoo_chart_json_v8"] = "yahoo_chart_json_v8"
    data_version: Literal["quote_close"] = "quote_close"
    public_use_permission: Literal["unverified"] = "unverified"
    target_date: date
    as_of_date: date | None = None
    license_ids: tuple[str, ...] = PUBLIC_LICENSE_IDS
    attributions: tuple[AttributionEntry, ...] = REQUIRED_PUBLIC_ATTRIBUTIONS
    schema_version: Literal[2, 3] = 2

    @model_validator(mode="after")
    def _validate_closed_provenance(self) -> Self:
        expected = (
            PUBLIC_REQUEST_TICKERS if self.schema_version == 2 else MARKET_GROUP_REQUEST_TICKERS
        )
        if self.requested_tickers != expected:
            raise ValueError("requested_tickers must equal the fixed Yahoo request set")
        if self.supported_tickers != expected:
            raise ValueError("supported_tickers must equal the fixed versioned Yahoo set")
        if self.missing_tickers != PUBLIC_STRUCTURALLY_MISSING_TICKERS:
            raise ValueError("Yahoo v2 has no structurally missing ticker")
        if self.license_ids != PUBLIC_LICENSE_IDS:
            raise ValueError("Yahoo v2 must not claim a verified data license")
        attributions = (
            REQUIRED_PUBLIC_ATTRIBUTIONS if self.schema_version == 2 else MARKET_GROUP_ATTRIBUTIONS
        )
        if self.attributions != attributions:
            raise ValueError("attributions must equal the fixed Yahoo entry in display order")
        if self.as_of_date is not None and self.as_of_date > self.target_date:
            raise ValueError("source as-of date must not be after target date")
        return self


class PublicSectorSeriesBundle(BaseModel):
    """Derived close-only public input bundle; contains no OHLCV arrays."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[2] = 2
    source_id: Literal["yahoo-chart-daily-v2"] = PUBLIC_SECTOR_SOURCE_ID
    market_scope: Literal[MarketScope.PROVIDER_REPORTED_US_EQUITY] = (
        MarketScope.PROVIDER_REPORTED_US_EQUITY
    )
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
        if any(failure.ticker not in PUBLIC_REQUEST_TICKERS for failure in value):
            raise ValueError("overview bundle failures require overview identities")
        return tuple(sorted(value, key=lambda failure: failure.ticker.value))

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
            raise ValueError("public bundle must account for every fixed Yahoo request ticker")
        return self


class PublicPriceMetrics(BaseModel):
    """Source-neutral derived price metrics; no ticker or raw observations."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    price_return_1d: MetricValue
    price_return_5d: MetricValue
    price_return_21d: MetricValue
    price_return_63d: MetricValue
    price_excess_1d: MetricValue
    price_excess_5d: MetricValue
    price_excess_21d: MetricValue
    price_excess_63d: MetricValue
    price_relative_acceleration_5d: MetricValue
    price_realized_volatility_20d: MetricValue
    price_max_drawdown_20d: MetricValue


class PublicSectorMetrics(PublicPriceMetrics):
    """All price metric slots for one fixed sector identity."""

    ticker: SectorTicker

    @model_validator(mode="after")
    def _validate_ticker(self) -> Self:
        if self.ticker is BENCHMARK_TICKER:
            raise ValueError("public sector metrics cannot use SPY")
        return self


_ALL_PUBLIC_METRIC_FIELDS: Final[tuple[PublicMetricName, ...]] = tuple(PublicMetricName)
_WARMING_SUPPRESSED_PUBLIC_METRICS: Final[tuple[PublicMetricName, ...]] = (
    PublicMetricName.PRICE_RETURN_21D,
    PublicMetricName.PRICE_RETURN_63D,
    PublicMetricName.PRICE_EXCESS_21D,
    PublicMetricName.PRICE_EXCESS_63D,
    PublicMetricName.PRICE_RELATIVE_ACCELERATION_5D,
    PublicMetricName.PRICE_REALIZED_VOLATILITY_20D,
    PublicMetricName.PRICE_MAX_DRAWDOWN_20D,
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
        return self


class PublicGroupRegime(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    regime: SectorRegime
    strength_state: AxisState | None = None
    acceleration_state: AxisState | None = None
    policy_id: Literal["sector-regime-v1"] = "sector-regime-v1"
    missing_reason: MetricMissingReason | None = None

    @model_validator(mode="after")
    def _validate_regime(self) -> Self:
        if self.regime is SectorRegime.INSUFFICIENT:
            if (
                self.missing_reason is None
                or self.strength_state is not None
                or self.acceleration_state is not None
            ):
                raise ValueError("missing group regime requires a reason and no axes")
        else:
            states = {
                (AxisState.POSITIVE, AxisState.POSITIVE): SectorRegime.LEADING,
                (AxisState.POSITIVE, AxisState.NEGATIVE): SectorRegime.WEAKENING,
                (AxisState.NEGATIVE, AxisState.POSITIVE): SectorRegime.RECOVERING,
                (AxisState.NEGATIVE, AxisState.NEGATIVE): SectorRegime.LAGGING,
            }
            if (
                self.strength_state is None
                or self.acceleration_state is None
                or self.missing_reason is not None
                or states.get((self.strength_state, self.acceleration_state)) is not self.regime
            ):
                raise ValueError("group regime must match its axis states")
        return self


class PublicGroupRank(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    score: Decimal | None = None
    ordinal: int | None = Field(default=None, ge=1, le=14)
    comparable_group_count: int = Field(ge=0, le=14)
    used_horizons: tuple[RankHorizon, ...] = ()
    missing_reason: Literal["unavailable", "insufficient_comparables"] | None = None

    @field_validator("score", mode="before")
    @classmethod
    def _reject_score_bool(cls, value: object) -> object:
        return RelativeRank._reject_boolean_score(value)

    @field_validator("score")
    @classmethod
    def _normalize_score(cls, value: Decimal | None) -> Decimal | None:
        return RelativeRank._normalize_score(value)

    @model_validator(mode="after")
    def _validate_rank(self) -> Self:
        if self.score is None:
            if self.ordinal is not None or self.used_horizons or self.missing_reason is None:
                raise ValueError("missing group rank must be suppressed")
        elif (
            self.ordinal is None
            or self.ordinal > self.comparable_group_count
            or self.comparable_group_count < 8
            or self.used_horizons != (5, 21, 63)
            or self.missing_reason is not None
        ):
            raise ValueError("group rank requires three horizons and eight comparables")
        return self


class PublicMarketGroupRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    group_id: MarketGroupId
    name: str = Field(max_length=80)
    category: GroupCategory
    kind: GroupKind
    members: tuple[PublicAssetTicker, ...]
    scope: str = Field(max_length=250)
    availability: SectorAvailability
    metrics: PublicPriceMetrics
    primary_regime: PublicGroupRegime
    relative_rank: PublicGroupRank

    @model_validator(mode="after")
    def _validate_record(self) -> Self:
        definition = GROUP_BY_ID[self.group_id]
        if (self.name, self.category, self.kind, self.members, self.scope) != (
            definition.name,
            definition.category,
            definition.kind,
            definition.members,
            definition.scope,
        ):
            raise ValueError("public group metadata must match the fixed definition")
        values = [metric.value for _, metric in self.metrics]
        if self.availability is SectorAvailability.AVAILABLE:
            if (
                any(value is None for value in values)
                or self.primary_regime.regime is SectorRegime.INSUFFICIENT
            ):
                raise ValueError("available groups require every metric and regime")
        elif (
            any(value is not None for value in values)
            or self.primary_regime.regime is not SectorRegime.INSUFFICIENT
            or self.relative_rank.score is not None
        ):
            raise ValueError("unavailable groups must suppress metrics, regime and rank")
        return self


class PublicMarketGroupBundle(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    universe_version: Literal["market-groups-v1"] = "market-groups-v1"
    as_of_date: date
    available_group_count: int = Field(ge=0, le=14)
    comparable_group_count: int = Field(ge=0, le=14)
    records: tuple[PublicMarketGroupRecord, ...]

    @field_validator("records")
    @classmethod
    def _normalize_records(
        cls, value: tuple[PublicMarketGroupRecord, ...]
    ) -> tuple[PublicMarketGroupRecord, ...]:
        if len(value) != 14 or {record.group_id for record in value} != set(MARKET_GROUP_IDS):
            raise ValueError("flat view requires exactly fourteen fixed group identities")
        return tuple(sorted(value, key=lambda record: MARKET_GROUP_IDS.index(record.group_id)))

    @model_validator(mode="after")
    def _validate_coverage_and_ranks(self) -> Self:
        available = [r for r in self.records if r.availability is SectorAvailability.AVAILABLE]
        if self.available_group_count != len(available) or self.comparable_group_count != len(
            available
        ):
            raise ValueError("group coverage must match actual complete records")
        if any(r.relative_rank.comparable_group_count != len(available) for r in self.records):
            raise ValueError("all group rank denominators must match coverage")
        ranked = [r for r in self.records if r.relative_rank.score is not None]
        if len(available) >= 8:
            expected = sorted(available, key=lambda r: -(r.relative_rank.score or Decimal(0)))
            if len(ranked) != len(available) or [r.relative_rank.ordinal for r in expected] != list(
                range(1, len(available) + 1)
            ):
                raise ValueError("group ranks must follow score and fixed tie order")
        elif ranked:
            raise ValueError("too few groups must suppress ranks")
        return self


class PublicSectorDashboardSnapshot(BaseModel):
    """Immutable, derived-only machine snapshot for the limited public radar."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[2, 3] = 2
    snapshot_id: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    universe_version: Literal["select-sector-spdr-v1"] = SECTOR_UNIVERSE_VERSION
    input_kind: Literal["yahoo_daily_close"] = "yahoo_daily_close"
    source_id: Literal["yahoo-chart-daily-v2"] = PUBLIC_SECTOR_SOURCE_ID
    market_scope: Literal[MarketScope.PROVIDER_REPORTED_US_EQUITY] = (
        MarketScope.PROVIDER_REPORTED_US_EQUITY
    )
    actual_market_ohlcv: Literal[True] = True
    consolidated_market_data: Literal[False] = False
    as_of_date: date | None = None
    freshness: FreshnessState
    coverage: PublicCoverageSummary
    records: tuple[PublicSectorRecord, ...]
    primary_policy: RegimePolicy = PRIMARY_REGIME_POLICY
    provenance: PublicSourceProvenance
    market_groups: PublicMarketGroupBundle | None = None

    @model_serializer(mode="wrap")
    def _serialize_snapshot(self, handler: SerializerFunctionWrapHandler) -> dict[str, object]:
        data: dict[str, object] = handler(self)
        if self.market_groups is None:
            data.pop("market_groups", None)
        return data

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
        if (self.schema_version == 3) != (self.market_groups is not None):
            raise ValueError("schema3 requires groups and schema2 must omit groups")
        if self.provenance.schema_version != self.schema_version:
            raise ValueError("snapshot and source provenance versions must match")
        if self.market_groups is not None:
            if self.market_groups.as_of_date != self.as_of_date or self.coverage.status not in {
                SectorCoverageStatus.NORMAL,
                SectorCoverageStatus.PARTIAL,
            }:
                raise ValueError("groups require the same promotable market date")
            overview = {record.ticker: record for record in self.records}
            for group in self.market_groups.records:
                if len(group.members) == 1 and isinstance(group.members[0], SectorTicker):
                    original = overview[group.members[0]]
                    if (
                        group.availability is not original.availability
                        or group.metrics.model_dump()
                        != original.metrics.model_dump(exclude={"ticker"})
                        or group.primary_regime.model_dump()
                        != original.primary_regime.model_dump(exclude={"ticker"})
                    ):
                        raise ValueError("reused group metrics and regimes must match overview")
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
    "PUBLIC_LICENSE_IDS",
    "PUBLIC_REQUEST_TICKERS",
    "PUBLIC_SECTOR_PROVIDER",
    "PUBLIC_SECTOR_SOURCE_ID",
    "PUBLIC_STRUCTURALLY_MISSING_TICKERS",
    "PUBLIC_SUPPORTED_SECTOR_TICKERS",
    "REQUIRED_PUBLIC_ATTRIBUTIONS",
    "YAHOO_FINANCE_ATTRIBUTION",
    "AttributionEntry",
    "FreshnessState",
    "HttpsUrl",
    "MarketScope",
    "PublicAdjustmentPolicy",
    "PublicBarPoint",
    "PublicBarSeries",
    "PublicBuildIssueCode",
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
