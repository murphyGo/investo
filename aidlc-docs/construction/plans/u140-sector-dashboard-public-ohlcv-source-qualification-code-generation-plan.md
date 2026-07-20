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
| Tiingo EOD API | free Starter technically provides broad raw/adjusted EOD OHLCV within ample daily quotas, but all listed standard tiers are Internal Use Only and display redistribution starts at a paid USD 250/month plan | reject for the no-paid public gate (2026-07-19 Step 0) |
| Marketstack EOD API | free access technically provides one year of batch EOD raw/adjusted OHLCV at 100 requests/month, but Commercial Use begins on a paid plan and current linked Freeware terms restrict use to testing/evaluation without a public derived-display grant | reject under current written terms (2026-07-19 Step 0) |
| Massive Stocks API (formerly Polygon.io) | free Stocks Basic technically provides two years of all-US-ticker EOD aggregates at five calls/minute, but the individual license prohibits apps for other end users and third-party display/distribution of Market Data or derived analytics/research | reject until express written public derived-display consent (2026-07-19 Step 0) |
| EODHD EOD API | free Starter technically provides one year of single-symbol EOD OHLCV plus adjusted close at 20 calls/day, but the plan is Personal use and current terms prohibit display or redistribution by non-professional users without prior written approval | reject under current written terms (2026-07-19 Step 0) |
| Tradier Market Data API | uncharged brokerage-account access technically provides lifetime single-symbol daily OHLCV at 60-120 market-data requests/minute, but non-Partner API entitlement is personal use and public-release applications require Partner approval with no published no-cost public license | reject under current written terms (2026-07-19 Step 0) |
| StockData.org EOD API | free access provides 100 requests/day but only one month of EOD history; one year begins at paid Basic, and the current terms limit use to personal, non-commercial purposes without a public derived-display grant | reject under current written terms (2026-07-19 Step 0) |
| MarketData.app Historical Candles API | Free technically provides one year of split-adjusted OHLCV and 100 daily credits, but every self-service plan is Internal Use and end-user display/redistribution requires a custom annual Commercial plan plus applicable exchange licenses | reject for the no-paid public gate (2026-07-21 Step 0) |
| Barchart OnDemand `getHistory` API | technically provides daily ETF OHLCV with split/dividend controls, but free access is only a limited evaluation trial; production is usage-priced, and the general terms require prior written consent for publication/distribution | reject for the permanent-free and public-rights gates (2026-07-21 Step 0) |
| Databento Historical API / `EQUS.SUMMARY` | technically provides consolidated US-equities EOD `ohlcv-1d`, multi-symbol requests, and ample rate limits, but every historical byte is usage-billed after a one-time $125 credit that expires in six months; exact dataset public derived-display rights require separate catalog/license-manager confirmation | reject for the permanent-free gate and unproven exact public rights (2026-07-21 Step 0) |
| Intrinio EOD Historical Stock Prices | technically provides 50+ years of daily raw/adjusted OHLCV, corporate-action fields, and up to 100 rows per page, but production starts at USD 150/month for internal-only Individual access; external display begins on the paid Startup plan under an executed Order Form | reject for the permanent-free and free public-rights gates (2026-07-21 Step 0) |
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

Primary Tiingo references, checked 2026-07-19:

- `https://www.tiingo.com/documentation/end-of-day`
- `https://www.tiingo.com/pricing`
- `https://www.tiingo.com/products/end-of-day-stock-price-data`
- `https://app.tiingo.com/tos/`

Primary Marketstack/APILayer references, checked 2026-07-19:

- `https://docs.apilayer.com/marketstack/docs/api-endpoints-v2`
- `https://api.swaggerhub.com/apis/apilayer-863/MarketstackAPIv2/2.0.0/swagger.json`
- `https://marketstack.com/pricing/`
- `https://www.ideracorp.com/legal/APILayer`
- `https://www.ideracorp.com/~/media/IderaInc/Files/APILayer/Apilayer%20Master%20Software%20as%20a%20Service%20Subscription%20Agreement%20SaaS%20082523ns%20FORM`

Primary Massive references, checked 2026-07-19:

- `https://massive.com/pricing?product=stocks`
- `https://massive.com/docs/rest/stocks/aggregates/custom-bars`
- `https://massive.com/legal/individuals-terms-of-service`
- `https://massive.com/legal/market-data-terms-of-service`

Primary EODHD references, checked 2026-07-19:

- `https://eodhd.com/financial-apis/api-for-historical-data-and-volumes`
- `https://eodhd.com/pricing`
- `https://eodhd.com/financial-apis/terms-conditions`
- `https://eodhd.com/financial-apis/our-data-sources-and-data-partners`

Primary Tradier references, checked 2026-07-19:

- `https://docs.tradier.com/reference/brokerage-api-markets-get-history`
- `https://docs.tradier.com/docs/historical-data`
- `https://docs.tradier.com/docs/historical`
- `https://docs.tradier.com/docs/rate-limiting`
- `https://docs.tradier.com/docs/faq`
- `https://docs.tradier.com/docs/authentication`
- `https://docs.tradier.com/docs/attribution-guidelines`
- `https://production.tradier.com/individuals/web`
- `https://production.tradier.com/businesses/fintechs`
- `https://api.tradier.com/v2/applications/agreements?key=api_agreement`

Primary StockData.org references, checked 2026-07-19:

- `https://www.stockdata.org/documentation`
- `https://www.stockdata.org/pricing`
- `https://www.stockdata.org/tos`

Primary MarketData.app references, checked 2026-07-21:

- `https://www.marketdata.app/docs/api/stocks/candles/`
- `https://www.marketdata.app/docs/api/authentication/`
- `https://www.marketdata.app/docs/api/rate-limiting/`
- `https://www.marketdata.app/docs/account/free-accounts/`
- `https://www.marketdata.app/pricing/`
- `https://www.marketdata.app/terms/`
- `https://www.marketdata.app/docs/account/data-policies/data-redistribution/`
- `https://www.marketdata.app/terms/commercial-use-addendum/`

Primary Barchart OnDemand references, checked 2026-07-21:

- `https://www.barchart.com/ondemand/api/getHistory`
- `https://www.barchart.com/ondemand/data`
- `https://www.barchart.com/solutions/services/ondemand`
- `https://www.barchart.com/ondemand`
- `https://www.barchart.com/ondemand/faq`
- `https://www.barchart.com/solutions/legal/terms`
- `https://www.barchart.com/solutions/exchange-fees`

Primary Databento references, checked 2026-07-21:

- `https://databento.com/docs/venues-and-datasets/equs-summary`
- `https://databento.com/docs/examples/equities/closing-prices`
- `https://databento.com/docs/api-reference-historical`
- `https://databento.com/pricing`
- `https://databento.com/docs/faqs/usage-pricing-and-data-credits`
- `https://databento.com/docs/quickstart`
- `https://databento.com/docs/portal`
- `https://databento.com/docs/knowledge-base`

Primary Intrinio references, checked 2026-07-21:

- `https://docs.intrinio.com/documentation/web_api/get_security_stock_prices_v2`
- `https://intrinio.com/access-methods`
- `https://help.intrinio.com/whats-an-api-call-and-how-are-they-counted`
- `https://intrinio.com/pricing`
- `https://about.intrinio.com/terms`

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

#### Iteration 4 — Tiingo EOD API

- [x] Record owner, official docs, endpoint, auth, cost, quota, symbols, fields,
  cadence, adjustment semantics, attribution, caching, raw-retention, and derived
  public-display clauses with dated primary-source links.
- [x] Deduplicate the candidate against existing registry/spec/routing and u138.
- [x] Classify `ship-now`, `defer`, or `reject` with one evidence-backed reason.

Recorded in
`aidlc-docs/construction/u140-sector-dashboard-public-ohlcv-source-qualification/source-qualification/2026-07-19-tiingo.md`.
Disposition: **reject**. Free Starter has sufficient structured EOD fields, history,
and request capacity, but Tiingo classifies every listed standard tier as Internal
Use Only and prohibits public analysis/display under its current terms. Display
redistribution requires special permission and a paid plan listed from USD 250/month,
so both the free and public-rights gates fail. Step 1 does not apply to this candidate.

#### Iteration 5 — Marketstack EOD API

- [x] Record owner, official docs, endpoint, auth, cost, quota, symbols, fields,
  cadence, adjustment semantics, attribution, caching, raw-retention, and derived
  public-display clauses with dated primary-source links.
- [x] Deduplicate the candidate against existing registry/spec/routing and u138.
- [x] Classify `ship-now`, `defer`, or `reject` with one evidence-backed reason.

Recorded in
`aidlc-docs/construction/u140-sector-dashboard-public-ohlcv-source-qualification/source-qualification/2026-07-19-marketstack.md`.
Disposition: **reject under current written terms**. The free tier's batch EOD API,
one-year range, and 100-request monthly allowance clear the preliminary technical
gate, but Commercial Use is a paid-plan feature and the current linked APILayer
Freeware terms permit testing/evaluation rather than a public Pages product. No
explicit free public derived-display or redistribution grant exists. Step 1 does not
apply to this candidate.

#### Iteration 6 — Massive Stocks API

- [x] Record owner, official docs, endpoint, auth, cost, quota, symbols, fields,
  cadence, adjustment semantics, attribution, caching, raw-retention, and derived
  public-display clauses with dated primary-source links.
- [x] Deduplicate the candidate against existing registry/spec/routing and u138.
- [x] Classify `ship-now`, `defer`, or `reject` with one evidence-backed reason.

Recorded in
`aidlc-docs/construction/u140-sector-dashboard-public-ohlcv-source-qualification/source-qualification/2026-07-19-massive-stocks.md`.
Disposition: **reject under current written terms**. Free Stocks Basic clears the
preliminary history, field, and request-budget gates, but the individual license is
personal-only and explicitly prohibits applications for other end users and
third-party display/distribution of both Market Data and derived analytics or
research. No express written Investo consent exists. Step 1 does not apply to this
candidate.

#### Iteration 7 — EODHD EOD API

- [x] Record owner, official docs, endpoint, auth, cost, quota, symbols, fields,
  cadence, adjustment semantics, attribution, caching, raw-retention, and derived
  public-display clauses with dated primary-source links.
- [x] Deduplicate the candidate against existing registry/spec/routing and u138.
- [x] Classify `ship-now`, `defer`, or `reject` with one evidence-backed reason.

Recorded in
`aidlc-docs/construction/u140-sector-dashboard-public-ohlcv-source-qualification/source-qualification/2026-07-19-eodhd.md`.
Disposition: **reject under current written terms**. Free Starter has sufficient
history, fields, freshness documentation, and daily calls for the 12-symbol workload,
but it is Personal use and the terms prohibit non-professional users from displaying
or redistributing original or repackaged Information. Professional display requires
prior written approval, which Investo does not have. Step 1 does not apply to this
candidate.

#### Iteration 8 — Tradier Market Data API

- [x] Record owner, official docs, endpoint, auth, cost, quota, symbols, fields,
  cadence, adjustment semantics, attribution, caching, raw-retention, and derived
  public-display clauses with dated primary-source links.
- [x] Deduplicate the candidate against existing registry/spec/routing and u138.
- [x] Classify `ship-now`, `defer`, or `reject` with one evidence-backed reason.

Recorded in
`aidlc-docs/construction/u140-sector-dashboard-public-ohlcv-source-qualification/source-qualification/2026-07-19-tradier.md`.
Disposition: **reject under current written terms**. Tradier's account-holder API has
sufficient historical OHLCV depth and request capacity, but non-Partner access is
personal use. A public-release application requires Partner approval, and the
business integration path provides no published zero-cost public-display license.
Attribution guidance is not a substitute for that authorization. Step 1 does not
apply to this candidate.

#### Iteration 9 — StockData.org EOD API

- [x] Record owner, official docs, endpoint, auth, cost, quota, symbols, fields,
  cadence, adjustment semantics, attribution, caching, raw-retention, and derived
  public-display clauses with dated primary-source links.
- [x] Deduplicate the candidate against existing registry/spec/routing and u138.
- [x] Classify `ship-now`, `defer`, or `reject` with one evidence-backed reason.

Recorded in
`aidlc-docs/construction/u140-sector-dashboard-public-ohlcv-source-qualification/source-qualification/2026-07-19-stockdata-org.md`.
Disposition: **reject under current written terms**. Free provides enough daily
requests for the 12-symbol workload but only one month of EOD history, so it cannot
meet the 63-trading-day gate. One year begins at paid Basic. The current terms also
limit use to personal, non-commercial purposes and provide no public derived-display
grant. Step 1 does not apply to this candidate.

#### Iteration 10 — MarketData.app Historical Candles API

- [x] Record owner, official docs, endpoint, auth, cost, quota, symbols, fields,
  cadence, adjustment semantics, attribution, caching, raw-retention, and derived
  public-display clauses with dated primary-source links.
- [x] Deduplicate the candidate against existing registry/spec/routing and u138.
- [x] Classify `ship-now`, `defer`, or `reject` with one evidence-backed reason.

Recorded in
`aidlc-docs/construction/u140-sector-dashboard-public-ohlcv-source-qualification/source-qualification/2026-07-21-marketdata-app.md`.
Disposition: **reject under current written terms**. Free provides enough history,
fields, and credits for the 12-symbol workload, but every self-service plan is
Internal Use. End-user display and redistribution require a custom annual Commercial
plan plus applicable exchange licenses, so the no-paid and explicit free public-use
gates fail before probing. Step 1 does not apply to this candidate.

#### Iteration 11 — Barchart OnDemand `getHistory` API

- [x] Record owner, official docs, endpoint, auth, cost, quota, symbols, fields,
  cadence, adjustment semantics, attribution, caching, raw-retention, and derived
  public-display clauses with dated primary-source links.
- [x] Deduplicate the candidate against existing registry/spec/routing and u138.
- [x] Classify `ship-now`, `defer`, or `reject` with one evidence-backed reason.

Recorded in
`aidlc-docs/construction/u140-sector-dashboard-public-ohlcv-source-qualification/source-qualification/2026-07-21-barchart-ondemand.md`.
Disposition: **reject under current published terms**. `getHistory` technically
supports daily stock/ETF OHLCV plus explicit split and dividend adjustments, but the
only published free access is a limited-request evaluation trial. Production access
is usage-priced, while the general terms require prior express written consent for
publication or distribution. The permanent-free and explicit free public-use gates
therefore fail before probing. Step 1 does not apply to this candidate.

#### Iteration 12 — Databento Historical API / `EQUS.SUMMARY`

- [x] Record owner, official docs, endpoint, auth, cost, quota, symbols, fields,
  cadence, adjustment semantics, attribution, caching, raw-retention, and derived
  public-display clauses with dated primary-source links.
- [x] Deduplicate the candidate against existing registry/spec/routing and u138.
- [x] Classify `ship-now`, `defer`, or `reject` with one evidence-backed reason.

Recorded in
`aidlc-docs/construction/u140-sector-dashboard-public-ohlcv-source-qualification/source-qualification/2026-07-21-databento-historical.md`.
Disposition: **reject under current published cost and rights evidence**.
`EQUS.SUMMARY` technically supplies consolidated US-equities EOD OHLCV, one-year
multi-symbol queries, and ample rate limits. Historical data is nevertheless billed
per byte after a one-time $125 credit that expires in six months, so no durable free
production tier exists. Redistribution rights are dataset-specific, and the reviewed
public pages do not expressly grant free public derived display for `EQUS.SUMMARY`.
The permanent-free gate fails and exact rights remain unproven before probing. Step 1
does not apply to this candidate.

#### Iteration 13 — Intrinio EOD Historical Stock Prices

- [x] Record owner, official docs, endpoint, auth, cost, quota, symbols, fields,
  cadence, adjustment semantics, attribution, caching, raw-retention, and derived
  public-display clauses with dated primary-source links.
- [x] Deduplicate the candidate against existing registry/spec/routing and u138.
- [x] Classify `ship-now`, `defer`, or `reject` with one evidence-backed reason.

Recorded in
`aidlc-docs/construction/u140-sector-dashboard-public-ohlcv-source-qualification/source-qualification/2026-07-21-intrinio-eod-historical-stock-prices.md`.
Disposition: **reject under current published pricing and terms**. The security-price
endpoint technically supplies daily raw and split/dividend-adjusted OHLCV plus
corporate-action fields, and the product advertises more than 50 years of history.
There is no permanent free production tier: the Individual plan is USD 150/month and
explicitly excludes redistribution or external display. Display rights begin on the
paid Startup plan, currently USD 333/month to start, and the terms require an executed
Order Form for third-party display, redistribution, or public derived outputs. The
permanent-free and explicit free public-use gates fail before probing. Step 1 does not
apply to this candidate.

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
