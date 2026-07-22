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
| SimFin Daily Share Prices | Free technically offers five years of daily US share-price history, API/bulk access, OHLC, adjusted close, and volume, but FREE/BASIC permits personal research only and forbids sharing; reprocessed data keeps the same restrictions, while redistribution requires a separate commercial redistribution/Enterprise license | reject for the explicit free public-rights gate (2026-07-21 Step 0) |
| FinancialData.Net ETF Prices API | technically provides an exact SPY/ETF daily OHLCV route, more than ten years of history, and up to 300 records per response, but ETF Prices is Premium at USD 69/month or USD 599/year; external display and redistribution are Enterprise-only at USD 299/month or USD 2,599/year | reject for the permanent-free and explicit free public-rights gates (2026-07-21 Step 0) |
| HF Data Library daily OHLCV | free API, 23+ years, daily aggregation, CC BY 4.0 plus IEX historical-data distribution with attribution, and current public metadata; however the required universe is 11/12 because `XLRE` is absent, and post-2022 volume is IEX-only at roughly 2–3% of consolidated volume | defer for exact-universe and volume-fitness repair (2026-07-22 Step 0) |
| BusinessQuant Stock Quotes API | free authenticated API technically advertises multi-year US-listed ETF EOD OHLCV, multi-ticker responses, and a 30-call daily Free budget; however the binding Terms grant no license in accessed data and pricing places commercial API use on Enterprise while treating commercial redistribution as plan-controlled | reject for the explicit free public-rights gate (2026-07-22 Step 0) |
| London Strategic Edge Free Market Data API | one free key technically advertises daily JSON/CSV OHLCV, 5,000 rows/request, history back to 2003, and 25 ETFs; however the Terms prohibit redistribution and derivative works without express written consent and leave upstream ETF-data provenance unverified | reject for the explicit free public-rights gate (2026-07-22 Step 0) |
| Direct IEX Exchange HIST / TOPS | free T+1 downloads, 12 months of history, and distribution with mandatory attribution pass preliminary cost/rights checks; however each date is a whole-market gzip PCAP of roughly 9–21 GB, not ticker-filtered daily bars, and derived activity is IEX-only rather than consolidated | reject for current public-MVP operational and metric fitness (2026-07-22 Step 0) |
| MIAX Pearl Equities Historical Market Data | official ToM/DoM history provides up to the most recent six months of venue messages, but costs USD 500 per MIAX-provided eight-terabyte USB device, requires exchange data agreements, is not an automated daily-bar endpoint, and remains MIAX-only | reject for permanent-free, automated-delivery, and unproven public-rights gates (2026-07-22 Step 0) |
| Cboe DataShop Equity EOD Summary | technically offers daily U.S. equity/ETF OHLC, trade volume, VWAP, and bid/ask history from January 2010 through historical purchases or subscriptions, but has no free entitlement; even eligible academic use carries a USD 500 minimum and public distribution remains agreement/license controlled | reject for permanent-free and explicit free public-rights gates (2026-07-22 Step 0) |
| MEMX MEMOIR Historical Data | official prior-day Depth/Top/Last Sale history is available through cloud APIs, but requires a Market Data Agreement and approved Order Form/System Description; public-use fees/approval are feed-specific and derived bars remain MEMX-only raw-message aggregates | reject for current public-MVP cost/rights certainty and metric fitness (2026-07-22 Step 0) |
| NYSE Daily TAQ | official consolidated CTA/UTP T+1 trades/quotes/NBBO archive covers U.S. securities from 1993, but the commercial subscription is USD 3,800/month with a 12-month minimum, older history and external historical redistribution are separately charged/licensed, and whole-market tick files are not bounded ticker-filtered bars | reject for permanent-free, explicit free public-rights, and operational-budget gates (2026-07-22 Step 0) |
| NYSE TAQ Closing Prices | official per-exchange daily Open/High/Low/Last, Total Volume, and closing quote summaries have NYSE Arca history since 2008 and bounded files, but cost USD 500/month under a 12-month minimum, external historical distribution requires a specific license/fee, and volume is NYSE-venue-local rather than consolidated | reject for permanent-free, explicit free public-rights, and volume-semantics gates (2026-07-22 Step 0) |
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

Primary SimFin references, checked 2026-07-21:

- `https://www.simfin.com/en/prices/`
- `https://www.simfin.com/en/commercial-license/`
- `https://www.simfin.com/en/fundamental-data-download/`
- `https://github.com/SimFin/simfin`
- `https://www.simfin.com/en/technical-updates-to-api-v3-and-bulk-download/`

Primary FinancialData.Net references, checked 2026-07-21:

- `https://financialdata.net/documentation`
- `https://financialdata.net/pricing`
- `https://financialdata.net/terms-of-service`
- `https://financialdata.net/stock-prices-api`

Primary HF Data Library references, checked 2026-07-22:

- `https://hfdatalibrary.com/`
- `https://hfdatalibrary.com/pages/api`
- `https://hfdatalibrary.com/pages/license`
- `https://hfdatalibrary.com/pages/terms`
- `https://hfdatalibrary.com/pages/issues`
- `https://github.com/elkassabgi/hfdatalibrary`
- `https://www.iex.io/legal/hist-data-terms`

Primary BusinessQuant references, checked 2026-07-22:

- `https://businessquant.com/docs/api/quotes`
- `https://businessquant.com/docs/api/universe`
- `https://businessquant.com/pricing`
- `https://businessquant.com/terms-of-use`

Primary London Strategic Edge references, checked 2026-07-22:

- `https://londonstrategicedge.com/free-market-data-api/`
- `https://londonstrategicedge.com/api/`
- `https://londonstrategicedge.com/data/`
- `https://londonstrategicedge.com/terms-of-service`

Primary direct IEX HIST references, checked 2026-07-22:

- `https://www.iex.io/products/equities/market-data-connectivity`
- `https://www.iex.io/legal/hist-data-terms`
- `https://iextrading.com/trading/market-data/`
- `https://www.iex.io/resources/trading/market-data`
- `https://iextrading.com/trading/eligible-symbols/`

Primary MIAX Pearl Equities historical-data references, checked 2026-07-22:

- `https://www.miaxglobal.com/markets/us-equities/pearl-equities/historical-market-data`
- `https://www.miaxglobal.com/markets/us-equities/pearl-equities/market-data`
- `https://www.miaxglobal.com/markets/us-equities/pearl-equities/market-data-vendor-agreements`
- `https://www.miaxglobal.com/markets/us-equities/pearl-equities/fees`
- `https://www.miaxglobal.com/sites/default/files/fee_schedule-files/MIAX_Pearl_Equities_Fee_Schedule_05012026_0.pdf`

Primary Cboe DataShop Equity EOD Summary references, checked 2026-07-22:

- `https://datashop.cboe.com/equity-eod-summary`
- `https://datashop.cboe.com/faqs`
- `https://datashop.cboe.com/academic-discount`
- `https://datashop.cboe.com/equity-etf-quotes`
- `https://www.cboe.com/market_data_services/document_library/`

Primary MEMX MEMOIR Historical Data references, checked 2026-07-22:

- `https://info.memxtrading.com/equities-trading-resources/us-equities-faq/`
- `https://info.memxtrading.com/memx-user-manual/`
- `https://info.memxtrading.com/equities-trading-resources/us-equities-fee-schedule/`
- `https://info.memxtrading.com/membership-connectivity-and-market-data-documents/`
- `https://info.memxtrading.com/wp-content/uploads/2023/01/MEMX-Market-Data-Policies.pdf`
- `https://info.memxtrading.com/wp-content/uploads/2026/06/MEMX-Rulebook-6.22.26clean.pdf`

Primary NYSE Daily TAQ references, checked 2026-07-22:

- `https://www.nyse.com/data-products/catalog/daily-taq`
- `https://www.nyse.com/market-data/historical`
- `https://www.nyse.com/publicdocs/nyse/data/NYSE_Historical_Market_Data_Pricing.pdf`
- `https://www.nyse.com/publicdocs/nyse/data/Daily_TAQ_Client_Spec_v4.1b.pdf`
- `https://www.nyse.com/publicdocs/nyse/data/Daily_TAQ_Client_Spec_v3.3b.pdf`
- `https://www.nyse.com/publicdocs/nyse/data/NYSE_Market_Data_Complete_Policy_Package.pdf`
- `https://www.nyse.com/market-data/pricing-policies-contracts-guidelines`

Primary NYSE TAQ Closing Prices references, checked 2026-07-22:

- `https://www.nyse.com/data-products/catalog/taq-nyse-closing-prices`
- `https://www.nyse.com/publicdocs/nyse/data/TAQ_Closing_Prices_Client_Spec_v2.1.pdf`
- `https://www.nyse.com/publicdocs/nyse/data/NYSE_Historical_Market_Data_Pricing.pdf`
- `https://www.nyse.com/publicdocs/nyse/data/NYSE_Market_Data_Complete_Policy_Package.pdf`
- `https://www.nyse.com/market-data/pricing-policies-contracts-guidelines`

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

#### Iteration 14 — SimFin Daily Share Prices

- [x] Record owner, official docs, endpoint, auth, cost, quota, symbols, fields,
  cadence, adjustment semantics, attribution, caching, raw-retention, and derived
  public-display clauses with dated primary-source links.
- [x] Deduplicate the candidate against existing registry/spec/routing and u138.
- [x] Classify `ship-now`, `defer`, or `reject` with one evidence-backed reason.

Recorded in
`aidlc-docs/construction/u140-sector-dashboard-public-ohlcv-source-qualification/source-qualification/2026-07-21-simfin-daily-share-prices.md`.
Disposition: **reject under the current FREE/BASIC data license**. Free access is
technically promising: SimFin publishes a zero-dollar account with five years of
history, daily open/high/low/close, adjusted close, volume, API/bulk access, and a
free API key path. The binding license permits FREE/BASIC data only for personal
research and prohibits sharing it with other parties. Reprocessed data remains under
the same disclosure restrictions; a redistribution license is separate, and SimFin
states that Enterprise is the only subscription that permits redistribution. The
license's undefined `interpretations` exception is not an explicit grant for public
numeric radar metrics, which may instead be reprocessed data. Exact ETF coverage and
the meaning of the Free bulk `delayed` label also remain unproven. The explicit free
public derived-display gate therefore fails before probing. Step 1 does not apply.

#### Iteration 15 — FinancialData.Net ETF Prices API

- [x] Record owner, official docs, endpoint, auth, cost, quota, symbols, fields,
  cadence, adjustment semantics, attribution, caching, raw-retention, and derived
  public-display clauses with dated primary-source links.
- [x] Deduplicate the candidate against existing registry/spec/routing and u138.
- [x] Classify `ship-now`, `defer`, or `reject` with one evidence-backed reason.

Recorded in
`aidlc-docs/construction/u140-sector-dashboard-public-ohlcv-source-qualification/source-qualification/2026-07-21-financialdata-net-etf-prices.md`.
Disposition: **reject under current published pricing and terms**. The documented
ETF endpoint is technically well matched: `GET /api/v1/etf-prices?identifier=SPY`
returns daily open, high, low, close, and volume, advertises more than ten years of
history, and allows up to 300 records per response. However, ETF Prices is explicitly
a Premium feature at USD 69/month or USD 599/year. The USD 0 Free plan's historical
price route covers company stocks, not ETFs. The terms prohibit public display and
distribution except where a subscription permits them, and the pricing page reserves
external commercial use, display, and redistribution for Enterprise at USD 299/month
or USD 2,599/year. Both binding gates fail before account creation or probing. Exact
12-symbol coverage, freshness, adjustment semantics, and runner stability remain
unproven. Step 1 does not apply.

#### Iteration 16 — HF Data Library daily OHLCV

- [x] Record owner, official docs, endpoint, auth, cost, quota, symbols, fields,
  cadence, adjustment semantics, attribution, caching, raw-retention, and derived
  public-display clauses with dated primary-source links.
- [x] Deduplicate the candidate against existing registry/spec/routing and u138.
- [x] Classify `ship-now`, `defer`, or `reject` with one evidence-backed reason.

Recorded in
`aidlc-docs/construction/u140-sector-dashboard-public-ohlcv-source-qualification/source-qualification/2026-07-22-hf-data-library.md`.
Disposition: **defer pending exact-universe and volume-fitness repair**. This is the
first candidate in the sequence to publish a plausible zero-cost public-use path:
the API is free at 100 downloads/minute, daily OHLCV is aggregated from one-minute
bars, history exceeds 23 years, CC BY 4.0 permits sharing and adaptation, and IEX's
upstream terms expressly permit distribution of post-March-2022 historical data with
the required attribution. Public repository metadata was current through 2026-07-20
and included SPY plus ten sector ETFs, but `XLRE` was absent, so fixed-universe
coverage is 11/12. The provider further discloses that post-2022 data represents only
IEX activity, roughly 2–3% of consolidated volume; it can have no-trade days and
OHLC values that differ from the full tape. Investo cannot label that field as total
ETF volume. Exact-universe coverage therefore fails before account/API probing, and
the volume metric needs an explicit venue-limited product contract. Step 1 does not
apply unless both blockers are resolved.

#### Iteration 17 — BusinessQuant Stock Quotes API

- [x] Record owner, official docs, endpoint, auth, cost, quota, symbols, fields,
  cadence, adjustment semantics, attribution, caching, raw-retention, and derived
  public-display clauses with dated primary-source links.
- [x] Deduplicate the candidate against existing registry/spec/routing and u138.
- [x] Classify `ship-now`, `defer`, or `reject` with one evidence-backed reason.

Recorded in
`aidlc-docs/construction/u140-sector-dashboard-public-ohlcv-source-qualification/source-qualification/2026-07-22-businessquant-stock-quotes.md`.
Disposition: **reject under current published terms and pricing**. The Quotes API is
technically promising: it advertises a free API-key path, strict historical EOD and
daily OHLCV modes, multi-ticker responses, US-listed ETF coverage, many years of
history, and EOD finalization within minutes of market close. The Free plan publishes
30 calls/day and 0.1 GB/month, enough for a bounded collection design even if its
two-simultaneous-ticker limit requires six requests. The binding Terms nevertheless
state that use grants no ownership or license in accessed content, information, or
data. Pricing separately places commercial API use on Enterprise and lists commercial
redistribution as a plan-controlled capability. That is not an explicit free public
derived-display grant for Investo Pages. The rights gate therefore fails before
account creation or payload probing. Exact 12-symbol coverage, adjustment semantics,
volume venue meaning, continuity, freshness, and runner stability remain unproven;
Step 1 does not apply.

#### Iteration 18 — London Strategic Edge Free Market Data API

- [x] Record owner, official docs, endpoint, auth, cost, quota, symbols, fields,
  cadence, adjustment semantics, attribution, caching, raw-retention, and derived
  public-display clauses with dated primary-source links.
- [x] Deduplicate the candidate against existing registry/spec/routing and u138.
- [x] Classify `ship-now`, `defer`, or `reject` with one evidence-backed reason.

Recorded in
`aidlc-docs/construction/u140-sector-dashboard-public-ohlcv-source-qualification/source-qualification/2026-07-22-london-strategic-edge.md`.
Disposition: **reject under current published terms**. The service technically looks
well matched: one free API key, OHLCV from one-minute through daily resolution, JSON
or CSV, up to 5,000 rows per request, history back to 2003 for long-listed instruments,
and 25 index/sector ETFs. Its binding Terms nevertheless prohibit redistributing,
reselling, or commercially exploiting data and forbid copying, modifying, distributing,
or creating derivative works without express written consent. The documented API
access is not an express free right to retain rows or publish derived sector metrics on
Investo Pages. The reviewed materials also do not identify the upstream ETF feed or
consolidated-volume semantics. Rights therefore fail before account or payload probing.
Exact 12-symbol coverage, endpoint grammar, adjustment, volume provenance, continuity,
freshness, and runner stability remain unproven; Step 1 does not apply.

#### Iteration 19 — Direct IEX Exchange HIST / TOPS

- [x] Record owner, official docs, endpoint, auth, cost, quota, symbols, fields,
  cadence, adjustment semantics, attribution, caching, raw-retention, and derived
  public-display clauses with dated primary-source links.
- [x] Deduplicate the candidate against existing registry/spec/routing and u138.
- [x] Classify `ship-now`, `defer`, or `reject` with one evidence-backed reason.

Recorded in
`aidlc-docs/construction/u140-sector-dashboard-public-ohlcv-source-qualification/source-qualification/2026-07-22-iex-hist-direct.md`.
Disposition: **reject for current public MVP operational and metric fitness**. IEX
officially provides free T+1 HIST downloads for the most recent 12 months and permits
distribution with mandatory attribution, so preliminary cost, history-depth, and
public-rights checks pass. The delivery unit nevertheless fails this product's bounded
collection contract: every date is a whole-market gzip PCAP requiring IEX-TP/TOPS
decoding and message-to-bar aggregation, and current catalog examples are roughly
9–21 GB for one TOPS trading day. A 63-day bootstrap therefore requires hundreds of
gigabytes before the 12 symbols can even be filtered. Resulting OHLCV would describe
IEX-only last sales, not consolidated ETF activity; routed executions and other
markets are excluded. Exact required-symbol trade continuity, corporate-action
adjustment, and usable-bar freshness remain unproven. The official catalog and feed
contract are sufficient to reject the current GHA-hosted public MVP path, so no HIST
file, payload, decoder fixture, local probe, or five-run GHA probe was created.

#### Iteration 20 — MIAX Pearl Equities Historical Market Data

- [x] Record owner, official docs, endpoint, auth, cost, quota, symbols, fields,
  cadence, adjustment semantics, attribution, caching, raw-retention, and derived
  public-display clauses with dated primary-source links.
- [x] Deduplicate the candidate against existing registry/spec/routing and u138.
- [x] Classify `ship-now`, `defer`, or `reject` with one evidence-backed reason.

Recorded in
`aidlc-docs/construction/u140-sector-dashboard-public-ohlcv-source-qualification/source-qualification/2026-07-22-miax-pearl-equities-historical-market-data.md`.
Disposition: **reject under current published cost, delivery, and rights terms**.
Official ToM/DoM historical data reaches the most recent six months and includes
last-sale/order-execution messages that could theoretically be aggregated into
venue-level OHLCV. The required product is nevertheless a USD 500 purchase delivered
on a MIAX-provided eight-terabyte USB device, not a free ticker-filtered daily API or
automatable download. Direct receipt requires an exchange data agreement and request
schedules, and external distribution has separate policy/fee obligations. Derived bars
would remain MIAX-only and require binary-feed decoding, cancellation handling, and a
separate corporate-action source. The permanent-free gate therefore fails before any
request, agreement, purchase, payload, exact-universe, local, or GHA probe; Step 1 does
not apply.

#### Iteration 21 — Cboe DataShop Equity EOD Summary

- [x] Record owner, official docs, endpoint, auth, cost, quota, symbols, fields,
  cadence, adjustment semantics, attribution, caching, raw-retention, and derived
  public-display clauses with dated primary-source links.
- [x] Deduplicate the candidate against existing registry/spec/routing and u138.
- [x] Classify `ship-now`, `defer`, or `reject` with one evidence-backed reason.

Recorded in
`aidlc-docs/construction/u140-sector-dashboard-public-ohlcv-source-qualification/source-qualification/2026-07-22-cboe-datashop-equity-eod-summary.md`.
Disposition: **reject under current published cost and licensing terms**. The product's
daily U.S. equity/ETF OHLC, trade volume, VWAP, bid/ask fields, CSV delivery, and
history since January 2010 are technically strong. Access is nevertheless an order or
subscription, not a permanently free endpoint. The only published discount reviewed
is limited to qualifying academic use, charges at least USD 500, and does not apply to
Investo. Cboe data agreements, policies, fees, and separate external-distribution use
remain applicable, with no explicit no-cost public derived-display grant. The binding
cost and rights gates therefore fail before account, cart, quote, order, sample,
exact-universe, posting-SLA, adjustment, volume-provenance, local, or GHA probes; Step
1 does not apply.

#### Iteration 22 — MEMX MEMOIR Historical Data

- [x] Record owner, official docs, endpoint, auth, cost, quota, symbols, fields,
  cadence, adjustment semantics, attribution, caching, raw-retention, and derived
  public-display clauses with dated primary-source links.
- [x] Deduplicate the candidate against existing registry/spec/routing and u138.
- [x] Classify `ship-now`, `defer`, or `reject` with one evidence-backed reason.

Recorded in
`aidlc-docs/construction/u140-sector-dashboard-public-ohlcv-source-qualification/source-qualification/2026-07-22-memx-memoir-historical-data.md`.
Disposition: **reject for current public MVP cost/rights certainty and metric
fitness**. MEMX officially offers prior-day Depth, Top, and Last Sale history through
cloud APIs, but access is not an anonymous ticker-filtered daily-bar surface. A market
data subscriber must execute an agreement and request connectivity; derived-data
distribution still requires an approved Order Form/System Description and can remain
subject to feed-specific fees. The current schedule charges USD 2,000/month for
external or digital-media distribution of Top/Last Sale. Even under an approved
non-fee-liable derived-data configuration, bars would be MEMX-only raw-message
aggregates requiring decoding, correction handling, and corporate-action input, not
consolidated ETF OHLCV. Cost/right certainty and metric fitness fail before agreement,
order-form, credential, payload, exact-universe, local, or GHA probes; Step 1 does not
apply.

#### Iteration 23 — NYSE Daily TAQ

- [x] Record owner, official docs, delivery, auth, cost, symbols, fields, cadence,
  adjustment semantics, attribution, retention, file size, and derived public-display
  clauses with dated primary-source links.
- [x] Deduplicate the candidate against existing registry/spec/routing and u138.
- [x] Classify `ship-now`, `defer`, or `reject` with one evidence-backed reason.

Recorded in
`aidlc-docs/construction/u140-sector-dashboard-public-ohlcv-source-qualification/source-qualification/2026-07-22-nyse-daily-taq.md`.
Disposition: **reject under current published pricing, licensing, and operational
budget**. Daily TAQ is the technically strongest consolidated candidate reviewed: the
official product contains CTA/UTP all-trades, all-quotes, and NBBO files for U.S.
securities, has history from 1993, and is delivered T+1. It is nevertheless a paid
whole-market archive. The commercial subscription costs USD 3,800/month under a
12-month minimum, older history is separately charged, and external historical
redistribution requires a specific NYSE license and fee. Representative daily files
are approximately 649 MB for Trades, 17 GB for Quotes, and 2.2 GB for NBBO, so deriving
12-symbol OHLCV would also violate the bounded GitHub Actions budget. The permanent-
free and explicit free public-rights gates fail before agreement, order, sample,
payload, exact-universe, local, or GHA probes; Step 1 does not apply.

#### Iteration 24 — NYSE TAQ Closing Prices

- [x] Record owner, official docs, delivery, auth, cost, symbols, fields, cadence,
  adjustment semantics, attribution, retention, volume meaning, and derived
  public-display clauses with dated primary-source links.
- [x] Deduplicate the candidate against NYSE Daily TAQ, existing routing, and u138.
- [x] Classify `ship-now`, `defer`, or `reject` with one evidence-backed reason.

Recorded in
`aidlc-docs/construction/u140-sector-dashboard-public-ohlcv-source-qualification/source-qualification/2026-07-22-nyse-taq-closing-prices.md`.
Disposition: **reject under current published cost, public-rights, and
volume-semantics terms**. The product avoids Daily TAQ's raw-tick scale: it publishes
one daily file per NYSE group exchange with Open/High/Low/Last, Total Volume, and
closing bid/ask fields, with NYSE Arca history from December 2008 and typical 10 p.m.
Eastern delivery. Access nevertheless costs USD 500/month under a 12-month minimum,
back history is separately charged, and external historical distribution requires a
specific NYSE license and relevant fee. The specification also defines Total Volume
as volume on that exchange, so the ETF bars remain NYSE Arca-venue summaries rather
than consolidated U.S. OHLCV. Cost, free public rights, and metric fitness fail before
dashboard registration, purchase, entitlement, sample, exact-universe, local, or GHA
probes; Step 1 does not apply.

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
