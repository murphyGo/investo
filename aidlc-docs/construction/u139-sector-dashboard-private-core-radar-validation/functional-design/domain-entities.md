# Domain Entities: `u139 sector-dashboard-private-core-radar-validation`

**Date**: 2026-07-18
**Status**: Complete — approved 2026-07-18
**Parent plan**: `aidlc-docs/construction/plans/u139-sector-dashboard-private-core-radar-validation-functional-design-plan.md`

## E1. `SectorTicker`

Closed symbol identity:

```text
XLC | XLY | XLP | XLE | XLF | XLV | XLI | XLB | XLRE | XLK | XLU | SPY
```

SPY is the benchmark. The other eleven values are sector members.

## E2. `SectorUniverse`

- `sectors: tuple[SectorTicker, ...]` in the fixed order above without SPY
- `benchmark: SectorTicker = SPY`
- `version: str = "select-sector-spdr-v1"`

Invariants:

- exactly eleven unique sector members;
- SPY absent from `sectors` and fixed as `benchmark`;
- no runtime extension or alias.

## E3. `PrivateWorkbookManifest`

- `schema_version: Literal[1]`
- `workbooks: Mapping[SectorTicker, AbsolutePath]`

Invariants:

- exactly twelve entries;
- absolute, unique `.xlsx` paths;
- manifest and paths never serialized into snapshot/report/logs;
- filename does not determine ticker.

## E4. `NavPoint`

- `trading_date: date`
- `nav: Decimal`

Invariants:

- finite positive NAV;
- date has no time/timezone;
- serialization is ISO date plus canonical decimal string.

## E5. `NavSeries`

- `ticker: SectorTicker`
- `points: tuple[NavPoint, ...]`
- `first_date: date`
- `latest_date: date`

Invariants:

- at least two points;
- strictly ascending unique dates;
- first/latest fields equal tuple endpoints;
- contains NAV only, no shares/AUM/volume/price field.

## E6. `WorkbookFailure`

- `ticker: SectorTicker`
- `issue_code: WorkbookIssueCode`
- `row_count: int | None`
- `first_date: date | None`
- `latest_date: date | None`

No path, cell coordinate, raw value, filename, or exception text is allowed.

## E7. `ParsedWorkbookSet`

- `series_by_ticker: Mapping[SectorTicker, NavSeries]`
- `failures: tuple[WorkbookFailure, ...]`

Exactly one success or failure exists for each manifest ticker. Ordering follows the
fixed universe, with SPY last in manifest processing and explicit as benchmark in
downstream views.

## E8. `SectorSeriesBundle`

- `universe_version: str`
- `input_kind: Literal["nav"]`
- `source_id: Literal["state-street-nav-history-private"]`
- `as_of_date: date | None`
- `benchmark: NavSeries | None`
- `sectors: tuple[NavSeries, ...]`
- `coverage: CoverageSummary`
- `diagnostics: tuple[PrivateDiagnostic, ...]`
- `input_fingerprint: str | None`

`input_fingerprint` is a deterministic digest of input bytes keyed in fixed ticker
order. It is private reproducibility metadata, not a provider payload or public
provenance claim. It is omitted when input validation stops before all selected files
can be safely hashed.

## E9. `CoverageStatus`

Closed values:

- `normal`
- `partial`
- `warming_up`
- `insufficient`

## E10. `CoverageSummary`

- `status: CoverageStatus`
- `available_sector_count: int`
- `expected_sector_count: Literal[11]`
- `benchmark_available: bool`
- `common_as_of: date | None`
- `benchmark_observation_count: int`
- `missing_tickers: tuple[SectorTicker, ...]`
- `reason_codes: tuple[str, ...]`

Reason codes are unique and sorted. Absolute paths and raw failures are absent.

## E11. `MetricValue`

- `value: Decimal | None`
- `missing_reason: MetricMissingReason | None`

Exactly one of `value` and `missing_reason` is populated.

Closed missing reasons:

- `coverage_insufficient`
- `warming_up`
- `benchmark_date_missing`
- `sector_date_missing`
- `insufficient_history`
- `numeric_invalid`

## E12. `SectorMetrics`

- `ticker: SectorTicker`
- `nav_return_1d/5d/21d/63d: MetricValue`
- `nav_excess_1d/5d/21d/63d: MetricValue`
- `nav_relative_acceleration_5d: MetricValue`
- `nav_realized_volatility_20d: MetricValue`
- `nav_max_drawdown_20d: MetricValue`

All values are ratios in the machine model. Renderers convert them to percent or
percentage-point labels without altering the snapshot.

## E13. `AxisState`

Closed values: `positive`, `negative`.

## E14. `SectorRegime`

Closed values:

- `leading`
- `weakening`
- `recovering`
- `lagging`
- `insufficient`

## E15. `RegimePolicy`

- `policy_id: str`
- `neutral_band_bps: Literal[0, 5, 10, 15, 20]`
- `relative_horizon: Literal[21]`
- `acceleration_horizon: Literal[5]`
- `hysteresis: Literal[True]`

Primary policy id is `sector-regime-v1` at 10 basis points. Sensitivity policy ids are
`sector-regime-v1-band-{bps}`.

## E16. `RegimeResult`

- `ticker: SectorTicker`
- `regime: SectorRegime`
- `strength_state: AxisState | None`
- `acceleration_state: AxisState | None`
- `policy_id: str`
- `missing_reason: MetricMissingReason | None`

Complete regimes require both axis states and no missing reason.

## E17. `RelativeRank`

- `score: Decimal | None`
- `ordinal: int | None`
- `comparable_sector_count: int`
- `used_horizons: tuple[Literal[5, 21, 63], ...]`
- `missing_reason: str | None`

Score is in `[0, 1]`. Ordinal is one-based and exists only with a score.

## E18. `SectorRecord`

- `ticker: SectorTicker`
- `metrics: SectorMetrics`
- `primary_regime: RegimeResult`
- `sensitivity_regimes: Mapping[int, SectorRegime]`
- `relative_rank: RelativeRank`
- `diagnostic_codes: tuple[str, ...]`

No provider input path, daily row, exchange field, flow field, or narrative is present.

## E19. `PrivateDiagnostic`

- `issue_code: str`
- `ticker: SectorTicker | None`
- `metric_name: str | None`
- `row_count: int | None`
- `first_date: date | None`
- `latest_date: date | None`

All optional fields are from the approved redacted set. Diagnostics sort by issue
code, ticker, then metric name.

## E20. `SectorDashboardSnapshot`

- `schema_version: Literal[1]`
- `universe_version: Literal["select-sector-spdr-v1"]`
- `input_kind: Literal["nav"]`
- `source_id: Literal["state-street-nav-history-private"]`
- `private_validation: Literal[True]`
- `actual_market_ohlcv: Literal[False]`
- `as_of_date: date | None`
- `coverage: CoverageSummary`
- `primary_policy: RegimePolicy`
- `records: tuple[SectorRecord, ...]`
- `diagnostics: tuple[PrivateDiagnostic, ...]`
- `input_fingerprint: str | None`

There is no wall-clock generation timestamp. Repeating the run with identical input,
policy, and code produces byte-identical JSON and Markdown.

## E21. `PrivateArtifactSet`

- `snapshot_path: Path`
- `report_path: Path`

Both paths live under one explicit private output directory. An artifact set is valid
only when both projections represent the same snapshot and neither path enters a
forbidden repository/public root.

## Cross-Entity Invariants

### I1. Identity completeness

Manifest validation establishes exactly twelve identities before private bytes are
read. Parse failure changes availability, not identity.

### I2. Same-as-of comparability

Every metric-bearing series has `latest_date == bundle.as_of_date`. Any successful
series mismatch makes the entire bundle non-comparable and suppresses calculations.

### I3. Benchmark endpoint integrity

Every metric window is defined by SPY dates and requires exact sector endpoints.

### I4. Projection equivalence

JSON and Markdown consume the same snapshot. Report ordering, labels, and grouping
cannot introduce a value absent from JSON.

### I5. Privacy non-interference

Paths and raw rows exist only in the input/parsing boundary and cannot be fields of
bundle, record, snapshot, diagnostic, or artifact content models.

### I6. Public-gate independence

No entity has a `public_ready`, `publishable`, or public-authorization field. u140
alone owns public price-data qualification.
