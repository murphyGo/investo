# Domain Entities: `u145 sector-dashboard-public-hf-limited-radar`

**Date**: 2026-07-22
**Status**: Complete

## E1. `PublicSourceId`

Closed value: `hf-data-library-iex-daily-v1`.

## E2. `MarketScope`

Closed values:

- `iex_venue_sample`
- `consolidated_us_market`

u145 v1 accepts only `iex_venue_sample`. The second value is reserved so a future migration
cannot silently change semantics under the same source id.

## E3. `PublicBarPoint`

- `trading_date: date`
- `open/high/low/close: Decimal`
- `volume: int`

It is an in-memory normalization type, not a public DTO. OHLC is finite positive; volume is
non-negative; bar bounds are internally consistent.

## E4. `PublicBarSeries`

- `ticker: SectorTicker`
- `points: tuple[PublicBarPoint, ...]`
- `first_date/latest_date: date`
- `market_scope: Literal["iex_venue_sample"]`
- `adjustment: PublicAdjustmentPolicy`

The exact adjustment enum values remain blocked until the credentialed payload/docs probe
confirms provider behavior. The type must not default an unknown policy to adjusted or raw.

## E5. `PublicSourceFailure`

- `ticker: SectorTicker`
- `issue_code: PublicSourceIssueCode`
- `retryable: bool`

Closed issue families include auth, throttle, transport, status, response_size, schema, row,
calendar, freshness, and insufficient_history. Provider messages and URLs are excluded.

## E6. `PublicParsedSet`

- `benchmark: PublicBarSeries | None`
- `sectors: Mapping[SectorTicker, PublicBarSeries]`
- `failures: tuple[PublicSourceFailure, ...]`

It accounts for the fixed requested eleven-symbol set. XLRE is absent by design and is not a
request failure.

## E7. `ValuePoint`

- `trading_date: date`
- `value: Decimal`

Source-neutral internal input to mathematical kernels. It has no NAV/price/volume label and is
never serialized directly.

## E8. `ValueSeries`

- `ticker: SectorTicker`
- `points: tuple[ValuePoint, ...]`

Constructed from `NavSeries.nav` for u139 wrappers and `PublicBarSeries.close` for u145. The
conversion owner retains the semantic context; renderers never consume `ValueSeries` directly.

## E9. `PublicSectorSeriesBundle`

- `schema_version: Literal[1]`
- `source_id: Literal["hf-data-library-iex-daily-v1"]`
- `market_scope: Literal["iex_venue_sample"]`
- `as_of_date: date | None`
- `benchmark: ValueSeries | None`
- `sectors: tuple[ValueSeries, ...]`
- `coverage: CoverageSummary`
- `failures: tuple[PublicSourceFailure, ...]`
- `provenance: PublicSourceProvenance`

It contains no raw OHLCV rows. XLRE appears in `coverage.missing_tickers` and not in sectors.

## E10. `PublicMetricName`

Closed values:

- `iex_price_return_1d/5d/21d/63d`
- `iex_price_excess_1d/5d/21d/63d`
- `iex_price_relative_acceleration_5d`
- `iex_price_realized_volatility_20d`
- `iex_price_max_drawdown_20d`

No volume or flow metric exists in v1.

## E11. `PublicSectorMetrics`

- `ticker: SectorTicker`
- one `MetricValue` for every E10 slot

`MetricValue`, `RegimePolicy`, `RegimeResult`, and `RelativeRank` may be reused from u139 because
they contain no NAV/source claim. `SectorMetrics` is not reused because its field names are
NAV-specific.

## E12. `SectorAvailability`

Closed values:

- `available`
- `temporarily_unavailable`
- `provider_unavailable`
- `insufficient_history`

XLRE is always `provider_unavailable` under source id v1.

## E13. `PublicSectorRecord`

- `ticker: SectorTicker`
- `availability: SectorAvailability`
- `metrics: PublicSectorMetrics`
- `primary_regime: RegimeResult`
- `relative_rank: RelativeRank`
- `diagnostic_codes: tuple[PublicDiagnosticCode, ...]`

Every fixed sector has exactly one record. Unavailable records suppress every metric, regime,
and rank value.

## E14. `AttributionEntry`

- `attribution_id: Literal["hf-data-library-cc-by-4.0", "iex-historical-data"]`
- `display_text: str`
- `url: HttpsUrl`
- `required: Literal[True]`

The exact IEX fixed text/link is copied from the accepted provider license evidence and pinned
by tests before publication.

## E15. `PublicSourceProvenance`

- `source_id/provider/market_scope`
- `requested_tickers/supported_tickers/missing_tickers`
- `adjustment: PublicAdjustmentPolicy`
- `target_date/as_of_date`
- `license_ids: tuple[str, ...]`
- `attributions: tuple[AttributionEntry, ...]`
- `schema_version: Literal[1]`

It contains neither retrieval wall-clock time nor request/account/secret data in the canonical
snapshot id. Operational logs may record a rounded duration separately.

## E16. `FreshnessState`

Closed values: `fresh`, `stale`, `unknown`.

## E17. `PublicSectorDashboardSnapshot`

- `schema_version: Literal[1]`
- `snapshot_id: sha256 | None`
- `universe_version: Literal["select-sector-spdr-v1"]`
- `input_kind: Literal["iex_daily_close"]`
- `source_id: Literal["hf-data-library-iex-daily-v1"]`
- `market_scope: Literal["iex_venue_sample"]`
- `actual_market_ohlcv: Literal[True]`
- `consolidated_market_data: Literal[False]`
- `as_of_date: date | None`
- `freshness: FreshnessState`
- `coverage: CoverageSummary`
- `records: tuple[PublicSectorRecord, ...]`
- `primary_policy: RegimePolicy`
- `provenance: PublicSourceProvenance`

Exactly eleven sector records are required. XLRE must be value-free and
`provider_unavailable`. A promotable snapshot must be `fresh` and `partial` or `normal`.

## E18. `RenderedPublicSectorProjection`

- `snapshot_bytes: bytes`
- `markdown_bytes: bytes`
- `snapshot_id: sha256`

Both byte sequences are canonical, UTF-8, newline-terminated where applicable, and validated
before persistence.

## E19. `PublicSectorBuildOutcome`

Closed variants:

- `promoted(snapshot_id, as_of_date)`
- `unchanged(snapshot_id, as_of_date)`
- `held_last_good(snapshot_id, as_of_date, failure_codes)`
- `blocked(failure_codes)`

Only promoted/unchanged are successful qualification outcomes. `held_last_good` preserves
reader availability but remains an operational failure signal.

## Cross-Entity Invariants

### I1. Fixed identity

Records equal the eleven fixed sector tickers; benchmark provenance is SPY; requested symbols
equal the supported HF v1 set.

### I2. Explicit structural absence

XLRE is missing from input series, present in records, marked `provider_unavailable`, and has no
metric/rank/complete regime value.

### I3. Semantic closure

Source id v1 implies `iex_venue_sample`, `consolidated_market_data=False`, IEX-labeled public
metric names, and both mandatory attribution entries.

### I4. Same-as-of

Every metric-bearing series ends on snapshot `as_of_date`; provenance, coverage, and snapshot
agree on that date.

### I5. Projection equivalence

JSON and Markdown are projections of the same snapshot id and cannot be promoted separately.

### I6. Raw-data exclusion

No public entity contains daily bar arrays, request/response material, secrets, or provider
account identity.

### I7. Private compatibility

`SectorSeriesBundle` and `SectorDashboardSnapshot` remain NAV/private literals; u145 adds sibling
types instead of broadening their source/input flags.
