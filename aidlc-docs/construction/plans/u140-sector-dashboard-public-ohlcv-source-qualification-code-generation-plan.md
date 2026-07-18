# Code Generation Plan: `u140 sector-dashboard-public-ohlcv-source-qualification`

**Date**: 2026-07-18
**Unit**: u140 sector-dashboard-public-ohlcv-source-qualification
**Stage**: Source qualification before Construction
**Status**: Blocked (no source has cleared every public-use gate)
**Source**: S0 source decision, FR-022, NFR-008, US-010
**Estimated Effort**: ~4-8 h per serious candidate; implementation estimate is
recorded only after source acceptance
**Dependencies**: u138 evidence is informative but not sufficient; u139 is independent

---

## Problem Statement

The public dashboard needs at least 63 daily OHLCV bars for the 11 Select Sector
SPDR ETFs plus SPY. Availability alone is insufficient: the selected source must be
free, structured, reachable from GitHub Actions, and supported by primary-source
terms that allow the intended derived values to appear on public GitHub Pages.

Current production endpoint repair in u138 restores existing briefing price paths,
but it neither proves the full sector universe nor grants public derived-display or
redistribution rights. u140 owns that distinct decision.

## Binding Source Gate

A candidate is accepted only when all checks pass:

1. Official documentation and terms identify the data owner, endpoint, auth, cost,
   attribution, caching, raw-retention, and public derived-display rights.
2. `XLC, XLY, XLP, XLE, XLF, XLV, XLI, XLB, XLRE, XLK, XLU, SPY` each return at least
   63 valid daily OHLCV bars with documented adjusted/unadjusted semantics.
3. Weekday freshness is at most 36 hours after the expected market close, with
   holiday behavior recorded.
4. Five GitHub Actions probes succeed within a fixed request and wall-clock budget;
   empty, malformed, throttled, and auth failures remain visible.
5. The source requires no paid plan, trial credential, browser automation, scraping
   bypass, hidden WebSocket protocol, or secret exposure.
6. Public artifacts retain only the allowed derived fields and required attribution;
   raw provider payload retention follows the accepted terms.

If any check fails or remains unclear, the unit stays blocked and no public sector
adapter or Pages construction is registered.

## Current Candidate Disposition

| Candidate | Evidence boundary | Disposition |
| --- | --- | --- |
| State Street NAV workbooks | official and structured, but local/private validation boundary; not exchange OHLCV | private u139 only |
| TradingView | widgets are display surfaces; Datafeed API expects customer-owned data; Broker REST is not a historical data API; automated collection is restricted | reject as Investo data source |
| Yahoo `query2` chart | existing operational path and useful reachability evidence; terms/public derived-display basis remains insufficient for this new Pages surface | defer; u138 only |
| Stooq | current quote endpoint 404; history path returns an automation challenge in observed probes | reject for the gate |
| Alpha Vantage / Twelve Data / similar individual free plans | structured APIs, but individual/free display and redistribution conditions do not currently clear this public product | reject until written terms fit |
| Finnhub stock candles | official structured OHLCV, but the endpoint is Premium-only; market-data plans are Personal Use and public/commercial use requires written approval | reject for the no-paid public gate (2026-07-19 Step 0) |
| Alpaca Market Data API | free Basic technically provides US stock/ETF history since 2016 and multi-symbol daily bars, but Alpaca says its API data cannot be redistributed and its customer agreement requires written consent for reproduction/distribution | reject until written public derived-display consent (2026-07-19 Step 0) |
| Financial Modeling Prep | free Basic technically provides five years of end-of-day history at 250 calls/day, but is classified as Individual use and public display/redistribution requires a separate Data Display and Licensing Agreement | reject until a written public derived-display agreement exists (2026-07-19 Step 0) |
| Nasdaq/Cboe website endpoints | public pages or delayed displays do not authorize automated extraction for this use | reject |

Primary TradingView references:

- `https://www.tradingview.com/support/solutions/43000474413-i-need-access-to-your-api-in-order-to-get-data-or-indicator-values/`
- `https://www.tradingview.com/charting-library-docs/latest/connecting_data/datafeed-api/`
- `https://www.tradingview.com/widget-docs/faq/data/`
- `https://www.tradingview.com/policies/`

Primary Finnhub references, checked 2026-07-19:

- `https://finnhub.io/docs/api/stock-candles`
- `https://finnhub.io/pricing`
- `https://finnhub.io/pricing-stock-api-market-data`
- `https://finnhub.io/register`

Primary Alpaca references, checked 2026-07-19:

- `https://docs.alpaca.markets/us/docs/about-market-data-api`
- `https://docs.alpaca.markets/us/reference/stockbars`
- `https://alpaca.markets/support/redistribute-alpaca-api`
- `https://files.alpaca.markets/disclosures/library/AcctAppMarginAndCustAgmt.pdf`

Primary Financial Modeling Prep references, checked 2026-07-19:

- `https://site.financialmodelingprep.com/developer/docs/pricing`
- `https://site.financialmodelingprep.com/developer/docs/terms-of-service`
- `https://site.financialmodelingprep.com/developer/docs/quickstart`
- `https://site.financialmodelingprep.com/developer/docs/stable/historical-price-eod-full`
- `https://site.financialmodelingprep.com/developer/docs/stable/historical-price-eod-non-split-adjusted`
- `https://site.financialmodelingprep.com/developer/docs/stable/historical-price-eod-dividend-adjusted`

## Qualification Steps

### Step 0 — Candidate fact sheet (repeat for each serious candidate)

#### Iteration 1 — Finnhub stock candles

- [x] Record owner, official docs, endpoint, auth, cost, quota, symbols, fields,
  cadence, adjustment semantics, attribution, caching, raw-retention, and derived
  public-display clauses with dated primary-source links.
- [x] Deduplicate the candidate against existing registry/spec/routing and u138.
- [x] Classify `ship-now`, `defer`, or `reject` with one evidence-backed reason.

Recorded in
`aidlc-docs/construction/u140-sector-dashboard-public-ohlcv-source-qualification/source-qualification/2026-07-19-finnhub.md`.
Disposition: **reject**. Historical stock OHLCV is a Premium endpoint and the listed
market-data licenses are Personal Use; the registration surface requires written
approval for commercial/professional use. This fails the free/public-rights gates
before any credentialed probe. Step 1 does not apply to this candidate.

#### Iteration 2 — Alpaca Market Data API

- [x] Record owner, official docs, endpoint, auth, cost, quota, symbols, fields,
  cadence, adjustment semantics, attribution, caching, raw-retention, and derived
  public-display clauses with dated primary-source links.
- [x] Deduplicate the candidate against existing registry/spec/routing and u138.
- [x] Classify `ship-now`, `defer`, or `reject` with one evidence-backed reason.

Recorded in
`aidlc-docs/construction/u140-sector-dashboard-public-ohlcv-source-qualification/source-qualification/2026-07-19-alpaca.md`.
Disposition: **reject under current written terms**. The free Basic plan and daily
bars clear the preliminary structure/cost check, but Alpaca's official support says
API data cannot be redistributed and the current customer agreement requires written
consent for reproduction or distribution. No explicit public derived-display grant
exists for Investo. Step 1 does not apply to this candidate.

#### Iteration 3 — Financial Modeling Prep

- [x] Record owner, official docs, endpoint, auth, cost, quota, symbols, fields,
  cadence, adjustment semantics, attribution, caching, raw-retention, and derived
  public-display clauses with dated primary-source links.
- [x] Deduplicate the candidate against existing registry/spec/routing and u138.
- [x] Classify `ship-now`, `defer`, or `reject` with one evidence-backed reason.

Recorded in
`aidlc-docs/construction/u140-sector-dashboard-public-ohlcv-source-qualification/source-qualification/2026-07-19-financial-modeling-prep.md`.
Disposition: **reject under current written terms**. Basic is free and exposes
end-of-day historical price/volume data, but the official pricing table classifies
the plan as Individual use and requires a separate Data Display and Licensing
Agreement for display or redistribution. The general terms independently prohibit
third-party-accessible application integration and multi-user display without a
specific agreement. Step 1 does not apply to this candidate.

#### Next candidate iteration

- [ ] Select the next non-duplicate candidate and repeat the complete Step 0 fact
  sheet. Only a candidate with a provisional `ship-now` rights/cost disposition may
  advance to Step 1.

### Step 1 — Local bounded probe (accepted Step 0 candidate only)

- [ ] Probe the exact 12-symbol universe and record status, content type, row count,
  as-of date, malformed/empty behavior, request count, and wall time.
- [ ] Validate OHLC domain, volume domain, duplicate dates, sort order, timezone,
  corporate-action adjustment, and 63-bar continuity.
- [ ] Keep raw probe output outside tracked/public roots unless terms explicitly
  permit a minimal redacted fixture.

### Step 2 — GitHub Actions reliability probe

- [ ] Run five bounded probes at representative times from the production runner.
- [ ] Record success ratio, freshness, throttle response, retry behavior, duration,
  and exact request budget without logging credentials or payload bodies.
- [ ] Reject a source that depends on bypassing anti-automation controls.

### Step 3 — Acceptance decision

- [ ] Confirm every binding gate with a reviewer-readable evidence table.
- [ ] If accepted, revise this plan and create required FD/NFR artifacts that fix
  adapter name/module, metadata, `SourceSpec`, tier/window/segment routing,
  diagnostics, fixtures, no-paid guard, and tests before Code Generation.
- [ ] If no source passes, keep u140 blocked and leave public S1-S5 construction
  unregistered; u139 private validation may continue independently.

## Post-Acceptance Quality Gates

These gates become executable only after the source and its fixed contracts are
recorded:

- focused adapter/spec/routing/fixture tests;
- 12-symbol and partial-coverage contract tests;
- no-paid/no-browser-automation guards;
- ruff, format check, mypy strict, full pytest, and `mkdocs build --strict`;
- public artifact audit for attribution and raw-provider-data leakage;
- five-run GHA evidence attached to the unit closeout.

## Exit Evidence

The unit can move from `Blocked` only with:

- a dated primary-source rights citation;
- 12/12 symbol and 63+ bar field evidence;
- five bounded GHA probe results;
- approved FD/NFR plus revised fixed module contracts;
- an explicit decision that raw payload handling and public derived fields satisfy
  NFR-008.
