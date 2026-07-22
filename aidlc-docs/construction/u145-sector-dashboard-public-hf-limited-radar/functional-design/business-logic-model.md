# Business Logic Model: `u145 sector-dashboard-public-hf-limited-radar`

**Date**: 2026-07-22
**Status**: Complete
**Requirements**: US-001, US-003, US-008, US-010, FR-001, FR-003, FR-022,
NFR-002, NFR-003, NFR-006, NFR-008
**Parent decision**: `aidlc-docs/inception/plans/us-sector-dashboard-s0-source-decision.md`

## 1. Objective

Build a limited public sector radar from HF Data Library daily bars while preserving
the truth that current bars represent IEX activity and that XLRE is unavailable. The
workflow requests a fixed supported set, validates one same-as-of close series against
SPY, reuses u139's deterministic mathematical kernels, creates a derived-only public
snapshot, and renders one static Pages document.

u145 does not turn the strict u140 gate green. It is a narrower product contract whose
coverage and venue limitations are visible in both machine and reader projections.

## 2. Inputs and Outputs

### Runtime input

- `HF_DATA_API_KEY` from an operator-owned GitHub Actions secret or local environment.
- Fixed request symbols: `SPY, XLB, XLC, XLE, XLF, XLI, XLK, XLP, XLU, XLV, XLY`.
- A target New York market date resolved independently from the briefing pipeline.
- Provider endpoint base fixed in code to `https://api.hfdatalibrary.com/v1`; no
  user-controlled URL, symbol, format, or query fragment.

### Provider normalization output

The adapter returns either one validated `PublicBarSeries` or one closed
`PublicSourceFailure` per requested ticker. Raw JSON/CSV/Parquet bytes and provider-shaped
objects do not leave the adapter call scope and are never written to disk.

### Public outputs

One successful build produces:

- `site_docs/sectors/index.md`: deterministic latest radar Markdown.
- `site_docs/sectors/latest.json`: deterministic derived-only machine snapshot.

The JSON contains aggregate metrics, rank/regime, coverage, freshness, and provenance.
It contains no daily OHLCV rows, API key, request URL, response headers, provider account
data, or raw response fragment.

## 3. End-to-End Workflow

### L1. Resolve configuration and fail before network

1. Resolve the expected fixed endpoint, ticker set, timeout, response ceiling, and
   conservative 100-requests/minute budget from code constants.
2. Read `HF_DATA_API_KEY` exactly once. Reject missing, blank, placeholder, whitespace,
   control-character, or overlong values without logging the value.
3. Resolve target date in `America/New_York`; never use wall-clock time as a snapshot id.
4. Stop before the first request when configuration validation fails.

### L2. Fetch the benchmark first

1. Request SPY daily bars with a bounded page/range contract fixed only after the live
   payload probe records the provider's exact parameters and schema.
2. Enforce HTTPS, host pinning, connect/read/total timeouts, status handling, byte ceiling,
   and JSON depth/row ceilings.
3. A missing or invalid SPY series makes the run `insufficient`; sector requests may be
   skipped because no relative metric can be published.

### L3. Fetch supported sectors with isolated failures

Request the ten supported sector tickers with bounded concurrency and a shared rate
budget. One sector failure does not erase successful siblings. XLRE is never requested:
its absence is a product contract, not a transient source error.

Each request yields exactly one of:

- `success(PublicBarSeries)`;
- `source_failure(code, ticker, retryable)`.

No arbitrary provider message crosses the adapter boundary.

### L4. Normalize daily bars

For every success:

1. Parse a date-only trading date and finite positive open/high/low/close values.
2. Require non-negative integer volume and `low <= open/close <= high`.
3. Sort ascending only if the source order is a documented complete reverse order;
   reject duplicates, interior disorder, unknown fields that alter shape, and mixed ticker
   identity.
4. Record the provider's observed adjustment semantics from the credentialed probe. Until
   that evidence exists, the implementation step remains blocked and may not assume split
   adjustment.
5. Retain at most the bounded calculation window in memory; discard raw fields after
   normalization.

### L5. Establish a common comparable date

The latest valid SPY date is the candidate `as_of`. A sector is metric-bearing only when
it has a close on that date and the required SPY calendar dates. A newer sector date does
not advance the snapshot past SPY. A stale benchmark, mixed future date, or target-date
violation makes the run insufficient.

XLRE is always in `missing_tickers` with reason `provider_unavailable`. Other missing
sectors use source/shape/calendar reason codes.

### L6. Resolve coverage

Precedence:

1. `insufficient`: SPY invalid/stale, fewer than 8 comparable sectors, or no safe `as_of`.
2. `warming_up`: SPY and at least 8 sectors exist but fewer than 64 benchmark observations
   are available.
3. `partial`: SPY and at least 8 sectors are metric-bearing with 64+ observations; this is
   the normal u145 launch state because XLRE is unavailable.

`normal` is reserved for a future source contract with all eleven sectors and is unreachable
for the fixed HF v1 catalog. The model retains the value so coverage semantics remain
compatible with u139 and future sources.

### L7. Reuse source-neutral mathematical kernels

Extract or expose source-neutral pure kernels from u139 without changing its public API:

- simple return;
- benchmark excess return;
- non-overlapping 5-day relative acceleration;
- annualized 20-day realized volatility;
- 20-day max drawdown;
- descending midrank percentiles;
- neutral-band regime classification and hysteresis.

Existing `nav_*` functions remain wrappers and existing u139 model fields/bytes remain
unchanged. u145 calls the kernels from `PublicBarSeries.close` values and stores results in
public `iex_price_*` fields so NAV and exchange-price semantics cannot be confused.

### L8. Compute public metrics

For each metric-bearing sector calculate:

- IEX price return: 1D, 5D, 21D, 63D;
- IEX price excess return versus SPY: 1D, 5D, 21D, 63D;
- current non-overlapping 5D SPY-excess return minus the immediately preceding 5D
  SPY-excess return;
- 20-day annualized IEX close-to-close realized volatility;
- 20-day max drawdown from IEX closes.

Volume is normalized only for provenance/diagnostics and is not passed to metric, rank,
regime, or summary builders in v1.

### L9. Compute regime and rank

Reuse `sector-regime-v1` with the 10 bps primary band and the same hysteresis transition
rules as u139. Relative rank uses 5D/21D/63D SPY-excess midrank percentiles with existing
weights and requires at least eight comparable sectors and two horizons per candidate.

XLRE and transiently missing sectors receive `insufficient` regime and missing rank. Rank
ordinals are among comparable sectors only; the UI prints the denominator explicitly.

### L10. Build provenance and freshness

One `PublicSourceProvenance` binds source id, provider, upstream venue scope, license ids,
required attribution text/links, requested/supported/missing tickers, observed adjustment
contract, retrieval target date, bar `as_of`, and schema version.

Freshness is computed from `as_of` and the expected U.S. market calendar, never from file
mtime. Values are `fresh`, `stale`, or `unknown`. `fresh` is required for a new promotion.

### L11. Render and validate projections

The Markdown and JSON are rendered from one immutable `PublicSectorDashboardSnapshot`.
Before staging, verify:

- exactly eleven sector records plus SPY provenance;
- XLRE unavailable and value-free;
- required `IEX venue sample`, partial-coverage, HF, CC BY 4.0, and IEX attribution text;
- absence of raw bars, volume-derived scores, flow language, secrets, and internal paths;
- shared snapshot id and deterministic serialization.

### L12. Promote or hold last-good

- Before the first valid build: any collection/validation failure writes nothing public.
- On a fresh valid build: stage both artifacts, validate the pair, then promote them in the
  same publication transaction used by the dedicated sector workflow.
- After at least one valid build: a failed/stale collection may preserve the existing
  derived pair byte-for-byte and update no `as_of`. The public page must already render a
  deterministic stale warning from a separately validated workflow status projection;
  it may not pretend the old pair is fresh.
- A malformed/mismatched existing pair is never retained as last-good.

Scheduled collection and Pages navigation remain disabled until five isolated GitHub
Actions probes have passed with the operator-owned key.

## 4. Failure Semantics

| Failure | Scope | Result |
| --- | --- | --- |
| missing/expired key, 401/403 | run | redacted auth failure; no new artifact |
| 429 or 5xx | request/run | bounded retry; failure remains visible |
| SPY missing/invalid/stale | bundle | insufficient; no new promotion |
| one sector malformed/unavailable | ticker | partial if at least 8 comparable sectors remain |
| XLRE absent | expected product state | unavailable card; never an alert by itself |
| fewer than 8 comparable sectors | bundle | insufficient; no rank/regime publication |
| attribution/provenance missing | projection | hard block |
| current collection failure with valid old pair | workflow | hold last-good with stale status; non-zero probe/collection outcome |

## 5. Non-Goals

No consolidated-volume claim, flow proxy, dollar volume, composite score, XLRE substitute,
provider fallback, raw-history archive, intraday updates, Telegram, LLM narrative, earnings
actual, constituent breadth, or coupling to the daily briefing pipeline.
