# Business Rules: `u139 sector-dashboard-private-core-radar-validation`

**Date**: 2026-07-18
**Status**: Complete — approved 2026-07-18
**Parent plan**: `aidlc-docs/construction/plans/u139-sector-dashboard-private-core-radar-validation-functional-design-plan.md`

## Input and Privacy Rules

### R1. Fixed universe

The manifest contains exactly `XLC, XLY, XLP, XLE, XLF, XLV, XLI, XLB, XLRE,
XLK, XLU, SPY`. SPY is the only benchmark. Case differences, aliases, additions,
and omissions are rejected rather than normalized silently.

### R2. Explicit manifest identity

Ticker identity comes only from the versioned manifest mapping. Filenames, workbook
titles, sheet names, and surrounding text do not override the mapping.

### R3. Absolute private paths

Manifest, workbook, and output paths are explicit. The manifest and workbooks must
resolve outside the repository; workbook paths must be absolute, unique regular
`.xlsx` files. Output must be outside the repository, `archive/`, `site_docs/`,
tracked fixtures, and every input path. Unsafe paths fail before any workbook is
opened.

### R4. No private payload persistence

The unit does not copy the manifest or workbook, record raw bytes, retain daily NAV
rows, or write provider-shaped fixtures. Tests use synthetic schema-equivalent XLSX
and typed in-memory series only.

### R5. Allowed columns

Only `Date` and `NAV` enter the canonical model. `Shares Outstanding`, `Total Net
Assets`, and every other workbook column are ignored and absent from snapshot,
report, diagnostics, and logs.

## Workbook Validation Rules

### R6. Header identity

Exactly one tabular header containing normalized `Date` and `NAV` is required.
Leading provider metadata rows are allowed. Duplicate matching headers or missing
required columns reject the ticker.

### R7. Date validity

Accepted rows require a real calendar date. Datetime values are reduced to their
calendar date only when the time component is midnight. Invalid, ambiguous, or
timezone-bearing cell text rejects the ticker.

### R8. NAV validity

NAV must be finite and strictly positive. Blank, boolean, formula-without-value,
NaN, infinity, zero, and negative values reject the ticker.

### R9. Row order and duplicates

Source rows may be strictly ascending or strictly descending. The parser converts
descending rows to ascending canonical order. Interior disorder and duplicate dates
reject the ticker; first/last-wins repair is forbidden.

### R10. Minimum series shape

A syntactically valid series contains at least two dated NAV points. Shorter input is
a ticker failure. Metric-specific history requirements remain separate.

## Bundle and Coverage Rules

### R11. SPY mandatory

SPY parse failure makes the bundle `insufficient`. Sector values are not interpreted
without their benchmark.

### R12. Strict newest-date alignment

Every successfully parsed series must have the same newest date as SPY. Any mismatch
sets bundle issue `bundle.as_of_mismatch`, suppresses metric/regime/rank output, and
forbids truncation to an older date or mixed-as-of comparison.

### R13. Coverage state precedence

Coverage resolves in this order:

1. `insufficient` on missing SPY or as-of mismatch.
2. `insufficient` on fewer than 8 valid sectors or fewer than 6 SPY observations.
3. `warming_up` on 8-11 valid sectors and 6-21 SPY observations.
4. `partial` on 8-10 valid sectors and at least 22 SPY observations.
5. `normal` on 11 valid sectors and at least 22 SPY observations.

### R14. Benchmark calendar

SPY trading dates define all horizon endpoints. Sector values are never interpolated,
forward-filled, or shifted to a nearby date.

## Metric Rules

### R15. Simple NAV returns

Horizon return is `latest_nav / horizon_nav - 1` for 1D, 5D, 21D, and 63D. SPY
excess return is sector return minus the matching SPY return over identical dates.

### R16. Non-overlapping acceleration

Five-day acceleration equals current 5D excess return minus the immediately preceding
non-overlapping 5D excess return. It requires sector and SPY NAV on benchmark offsets
0, 5, and 10.

### R17. Realized NAV volatility

Twenty-day volatility is the sample standard deviation of 20 daily log NAV returns,
annualized by `sqrt(252)`. It is always labeled `NAV 기준 실현변동성`.

### R18. NAV drawdown

Twenty-day max drawdown is the lowest `NAV / running_peak - 1` across the latest 21
benchmark dates. It is non-positive; zero means no decline from a running peak.

### R19. Missing metric values

A metric with missing required dates is `null` with a stable missing reason. It is
never zero, estimated, or omitted without explanation.

## Regime and Rank Rules

### R20. Regime policy identity

The primary policy id is `sector-regime-v1`, with a 10-basis-point neutral band.
Sensitivity policies use the same algorithm at 0, 5, 15, and 20 basis points.

### R21. Hysteresis

Each strength/acceleration axis changes positive only above `+band`, changes negative
only below `-band`, and otherwise retains its prior state. Initial eligible values use
raw sign; exactly zero initializes negative.

### R22. Closed regime set

The only regimes are `leading`, `weakening`, `recovering`, `lagging`, and
`insufficient`. The four complete states come from the two binary axes; missing 21D
excess or 5D acceleration produces `insufficient`.

### R23. Relative rank

`relative_rank_v1` weights excess-return percentiles 5D/21D/63D as
`0.20/0.50/0.30`. At least two windows and eight comparable sectors are required.
Weights are renormalized when a window is unavailable. Rank excludes volatility,
drawdown, flow, volume, sensitivity, and narrative.

### R24. Percentile ties

Percentiles use descending midrank with best `1` and worst `0`. Ties share the mean
of their occupied ranks. For `n` sectors and one-based descending midrank `r`, the
value is `(n - r) / (n - 1)`. A deterministic universe-order key breaks display ties
but does not change the numeric percentile.

## Output Rules

### R25. Single snapshot source

`snapshot.json` and `report.md` are projections of the same immutable
`SectorDashboardSnapshot`. Renderers may not recompute metrics or coverage.

### R26. Deterministic serialization

Dates use ISO format, decimals use canonical strings, keys/order are stable, and no
wall-clock timestamp or absolute input/output path enters the snapshot.

### R27. Mandatory labels

Every report begins with `private validation`, `NAV 수익률`, and `실제 시장 OHLCV
아님`. Volatility uses the NAV label. The report never uses `가격수익률`, `거래량`,
`거래대금`, `자금 유입`, `actual flow`, or a public-source claim.

### R28. Insufficient behavior

Insufficient or alignment-failed output contains only scope labels, coverage state,
as-of availability, and redacted diagnostics. It contains no rank, quadrant, regime,
top/bottom claim, or partial metric table.

### R29. Warming-up behavior

Warming-up output may show 1D/5D NAV returns and excess returns when available, but
hides formal rank, regime, quadrant, and top/bottom claims.

### R30. Sensitivity is private evidence

The 0/5/10/15/20 basis-point regime matrix is private review evidence. It does not
select a public policy automatically and does not alter u140.

## Diagnostics Rules

### R31. Stable issue codes

Diagnostics use stable codes from this closed family:

- `manifest.schema`
- `manifest.universe`
- `manifest.path`
- `output.forbidden_path`
- `workbook.open`
- `workbook.header`
- `workbook.date`
- `workbook.nav`
- `workbook.order`
- `workbook.duplicate_date`
- `bundle.spy_missing`
- `bundle.as_of_mismatch`
- `bundle.coverage_insufficient`
- `metric.insufficient_history`

### R32. Redacted diagnostics

Diagnostics may include issue code, ticker, row count, date range, coverage count,
and metric name. They never include paths, filenames, sheet/cell contents, raw values,
provider payload, or unsanitized exception text.

### R33. Existing pipeline non-interference

u139 does not register a source, join the orchestrator, write a public artifact,
change a briefing model, or call publisher/notifier code. Existing briefing and
public artifacts remain byte-unchanged by private validation execution.
