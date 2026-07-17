# Business Logic Model: `u139 sector-dashboard-private-core-radar-validation`

**Date**: 2026-07-18
**Status**: Complete — approved 2026-07-18
**Requirements**: FR-022, NFR-003, NFR-006, NFR-008, US-010
**Parent plan**: `aidlc-docs/construction/plans/u139-sector-dashboard-private-core-radar-validation-functional-design-plan.md`

## 1. Objective

Validate the sector-radar domain and reader contract with operator-provided local NAV
history while the public OHLCV gate remains blocked. The unit converts twelve private
workbooks into one canonical, same-as-of bundle; computes deterministic NAV-based
metrics, rank, regime, coverage, and sensitivity; then writes only a private JSON
snapshot and Markdown report outside the repository.

The workflow never downloads provider data, never modifies the daily briefing
pipeline, and never represents NAV-derived values as exchange price, volume, or flow.

## 2. Inputs and Outputs

### Input manifest

The operator supplies an untracked JSON manifest by explicit path:

```json
{
  "schema_version": 1,
  "workbooks": {
    "XLC": "/absolute/private/path/navhist-us-en-xlc.xlsx",
    "XLY": "/absolute/private/path/navhist-us-en-xly.xlsx",
    "XLP": "/absolute/private/path/navhist-us-en-xlp.xlsx",
    "XLE": "/absolute/private/path/navhist-us-en-xle.xlsx",
    "XLF": "/absolute/private/path/navhist-us-en-xlf.xlsx",
    "XLV": "/absolute/private/path/navhist-us-en-xlv.xlsx",
    "XLI": "/absolute/private/path/navhist-us-en-xli.xlsx",
    "XLB": "/absolute/private/path/navhist-us-en-xlb.xlsx",
    "XLRE": "/absolute/private/path/navhist-us-en-xlre.xlsx",
    "XLK": "/absolute/private/path/navhist-us-en-xlk.xlsx",
    "XLU": "/absolute/private/path/navhist-us-en-xlu.xlsx",
    "SPY": "/absolute/private/path/navhist-us-en-spy.xlsx"
  }
}
```

The manifest must contain exactly the fixed universe. Relative paths, extra keys,
unknown tickers, duplicate paths, and a missing SPY entry are terminal manifest
errors. Workbook filenames do not determine identity; the explicit ticker mapping is
authoritative.

### Private outputs

One successful run writes exactly:

- `snapshot.json`: canonical deterministic machine-readable projection.
- `report.md`: deterministic reader-facing private validation report.

The output directory is explicit and outside the repository/public roots. Neither
artifact contains input paths, workbook bytes, raw rows, or daily NAV history.

## 3. End-to-End Workflow

### L1. Validate paths before reading private data

1. Resolve the repository root and all supplied paths; require manifest, workbooks,
   and output to remain outside every repository/public/tracked root.
2. Validate manifest shape and the exact twelve-symbol key set.
3. Validate that every workbook path is absolute, unique, a regular file, and has an
   `.xlsx` suffix.
4. Validate that the output directory is explicit, outside the repository, and not a
   parent/child alias of an input path.
5. Stop before opening any workbook if manifest or output-path validation fails.

### L2. Parse each workbook independently

For each ticker in fixed universe order:

1. Locate exactly one header row containing `Date` and `NAV`. The additional observed
   columns `Shares Outstanding` and `Total Net Assets` may exist but are ignored.
2. Read `Date` and `NAV` only; never retain the additional columns.
3. Accept a strictly ascending or strictly descending source order and canonicalize
   it to ascending dates. Reject interior disorder or duplicate dates.
4. Require a valid calendar date and finite positive NAV for each accepted row.
5. Produce either a `NavSeries` or one redacted `WorkbookFailure` for the ticker.

Per-workbook failures are isolated so the coverage state machine can be exercised.
Manifest failures, unsafe paths, SPY failure, and cross-symbol as-of mismatch remain
bundle-level blockers.

### L3. Establish the canonical as-of date

1. SPY must parse successfully.
2. Collect the newest date from every successfully parsed series.
3. All collected newest dates must equal SPY's newest date.
4. If any successful series has a different newest date, emit
   `bundle.as_of_mismatch`, suppress every metric/regime/rank, and render only a
   redacted insufficient diagnostic report.
5. Otherwise the shared newest date becomes `as_of_date`.

No truncation to an older common date and no mixed-as-of calculation is allowed.

### L4. Resolve coverage

Coverage counts sector series only; SPY is a separate mandatory benchmark.

| State | Condition |
| --- | --- |
| `normal` | SPY + all 11 sectors are valid, same-as-of, and at least 22 SPY trading observations exist |
| `partial` | SPY + 8-10 sectors are valid, same-as-of, and at least 22 SPY trading observations exist |
| `warming_up` | SPY + at least 8 sectors are valid and same-as-of, with 6-21 SPY trading observations |
| `insufficient` | SPY unavailable, as-of mismatch, fewer than 8 sectors, or fewer than 6 SPY observations |

`normal` and `partial` permit metric/regime/rank calculation for available sectors.
`warming_up` permits 1D/5D display where available but suppresses 21D regime,
cross-sectional rank, and quadrant. `insufficient` suppresses all metric claims.

### L5. Select benchmark dates

SPY defines the canonical trading-date grid. A metric with horizon `h` uses the SPY
date at offset `h` from `as_of_date`. A sector metric is available only when that
sector has NAV values on every date required by its formula. Missing endpoints or
interior daily observations produce an explicit null with a reason; values are never
interpolated or forward-filled.

### L6. Compute NAV metrics

For sector `s`, benchmark `b=SPY`, latest date `t`, and horizon `h`:

```text
return_s(h) = NAV_s(t) / NAV_s(t-h) - 1
return_b(h) = NAV_b(t) / NAV_b(t-h) - 1
excess_s(h) = return_s(h) - return_b(h)
```

Availability:

| Metric | Required benchmark-grid NAV points |
| --- | ---: |
| 1D return/excess | 2 |
| 5D return/excess | 6 |
| 21D return/excess | 22 |
| 63D return/excess | 64 |
| 5D acceleration | dates at offsets 0, 5, and 10 |
| 20D realized volatility | 21 consecutive benchmark dates |
| 20D max drawdown | 21 consecutive benchmark dates |

Five-day relative acceleration is:

```text
current_excess_5d = return_s(t-5, t) - return_spy(t-5, t)
previous_excess_5d = return_s(t-10, t-5) - return_spy(t-10, t-5)
acceleration_5d = current_excess_5d - previous_excess_5d
```

Realized NAV volatility uses the sample standard deviation of the latest 20 daily
log NAV returns multiplied by `sqrt(252)`. Max drawdown is the minimum of
`NAV / running_peak - 1` over the same 21-point window.

### L7. Compute regime with hysteresis

The primary policy is `sector-regime-v1` with a 10-basis-point neutral band for both
21D excess return and 5D acceleration.

Each axis has a two-state sign carried forward through history:

1. Above `+band`: axis becomes positive.
2. Below `-band`: axis becomes negative.
3. Inside the closed neutral band: retain the prior axis state.
4. At the first eligible date, initialize from the raw sign; exactly zero initializes
   negative to preserve the product contract's `<= 0` branch.

Axis mapping:

| 21D relative strength | 5D acceleration | Regime |
| --- | --- | --- |
| positive | positive | `leading` |
| positive | negative | `weakening` |
| negative | positive | `recovering` |
| negative | negative | `lagging` |

Missing required values produce `insufficient`; a regime is never guessed.

### L8. Compute cross-sectional rank

`relative_rank_v1` uses only available excess-return horizons:

```text
0.20 * percentile(excess_5d)
+ 0.50 * percentile(excess_21d)
+ 0.30 * percentile(excess_63d)
```

- At least two horizons and at least eight comparable sectors are required.
- Missing horizon weights are renormalized over available horizons.
- Percentiles use descending midrank. For `n` sectors and one-based descending
  midrank `r`, `percentile = (n - r) / (n - 1)`; best is 1, worst is 0, and ties
  share the average occupied rank.
- Volatility, drawdown, sensitivity, and coverage never enter the rank.
- Warming-up and insufficient bundles have no formal rank.

### L9. Compute neutral-band sensitivity

Re-run only the regime classifier with bands `0, 5, 10, 15, 20` basis points. Metric
values and rank remain unchanged. The primary output is the 10-basis-point result;
the other bands appear in a private sensitivity matrix. This comparison does not
change or clear the public policy gate.

### L10. Serialize and render

1. Build one immutable `SectorDashboardSnapshot` from the canonical bundle.
2. Serialize dates as ISO strings and all decimal metric values as canonical decimal
   strings with no wall-clock field.
3. Sort sector records by formal rank descending when rank exists; use fixed universe
   order as the stable fallback and for tied/missing rows.
4. Render `snapshot.json` and `report.md` from the same snapshot object.
5. Verify both projections contain the mandatory private/NAV labels and no forbidden
   field or raw input reference.

## 4. Failure Semantics

| Failure | Scope | Result |
| --- | --- | --- |
| manifest schema/universe/path error | run | stop before workbook read; no output |
| output path enters repository/public root | run | stop before workbook read; no output |
| one sector workbook malformed | ticker | mark unavailable; continue to coverage resolution |
| SPY malformed/unavailable | bundle | `insufficient`; no metrics/rank/regime |
| successful series have mixed newest dates | bundle | `insufficient`; diagnostic-only report |
| fewer than 8 valid sectors | bundle | `insufficient`; no metrics/rank/regime |
| metric lacks required dates | metric | explicit null plus reason; no interpolation |
| private output write failure | run | fail without modifying existing complete artifact pair |

Diagnostics expose stable issue codes, ticker when safe, counts, and dates only. They
never expose absolute paths, workbook cell contents, raw rows, or exception strings
that contain private values.

## 5. Non-Goals

- Automated download or provider login.
- Exchange OHLCV, volume, dollar volume, actual flow, holdings, or earnings.
- Public HTML/SVG, Pages navigation, archive history, Telegram, or GitHub Actions.
- Persisted daily NAV series or a cross-run cache.
- Public source qualification; u140 owns that gate.
- Any read/write/import integration with the existing briefing collection,
  generation, publishing, notification, or scheduled workflow paths.
