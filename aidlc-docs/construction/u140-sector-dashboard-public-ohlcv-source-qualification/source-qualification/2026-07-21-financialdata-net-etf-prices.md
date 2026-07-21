# u140 Source Fact Sheet — FinancialData.Net ETF Prices

**Checked**: 2026-07-21
**Candidate**: FinancialData.Net ETF Prices API
**Disposition**: Reject under current published pricing and terms for public Pages
**Probe status**: Not run; the permanent-free and explicit free public derived-display gates failed before account or payload access

## Source Facts

| Field | Value |
| --- | --- |
| Source owner | Afinec, SP |
| Data family | End-of-day historical prices and volumes for major exchange-traded funds |
| Official docs | `https://financialdata.net/documentation`, `https://financialdata.net/pricing`, and `https://financialdata.net/terms-of-service` |
| Endpoint | `GET https://financialdata.net/api/v1/etf-prices?identifier=SPY` with optional `offset` and `format=json,csv` |
| Auth | Append `key=API_KEY` to the query string; an account and API key are required |
| Cost and no-paid evidence | The exact ETF Prices endpoint is labeled Premium. Personal Premium is USD 69/month or USD 599/year. The USD 0 Free plan includes symbol lists and market/miscellaneous data, and the separately documented free Stock Prices route covers companies rather than ETFs. The required ETF-history path therefore fails the permanent-free gate. |
| Rate and request budget | Premium publishes 30 requests/second. ETF Prices returns one identifier per request with up to 300 records, so 12 requests could preliminarily cover the required universe and 63-bar depth. No paid entitlement was obtained and request accounting was not probed. |
| Format | JSON by default or CSV through the optional `format` parameter |
| Key fields | `trading_symbol`, `date`, `open`, `high`, `low`, `close`, and `volume` |
| Required symbols | The documentation demonstrates SPY and describes several thousand major ETFs. The free ETF-symbol list exists, but exact availability of SPY plus the 11 SPDR sector ETFs was not established after the binding cost/rights failure. |
| Update cadence | Pricing describes end-of-day prices as daily and covered since 2015. The exact publication time and at-most-36-hour weekday freshness were not probed. |
| Historical range | More than ten years, with 300 records per response and offset pagination; technically exceeds 63 trading days |
| Adjustment semantics | The response exposes only OHLC and volume. The reviewed ETF Prices contract does not state split/dividend adjustment, adjusted-close, or adjusted-volume semantics. |
| Attribution | If separate permission to publicly display Content is granted, the terms require identifying FinancialData.Net as owner/licensor and keeping proprietary notices visible. Attribution alone does not create permission. |
| Caching and raw retention | The reviewed terms do not expressly grant a Free or Premium public-repository caching/retention right. Raw retention was not assumed and no payload was stored. |
| License/public display | Unless an applicable subscription expressly permits it, Content may not be copied, aggregated, republished, publicly displayed, transmitted, distributed, sold, licensed, or otherwise exploited. The pricing page grants External Commercial Use and Data Display & Redistribution only to Enterprise, at USD 299/month or USD 2,599/year. No zero-cost public or derived-display grant is published. |
| Existing Investo overlap | No FinancialData.Net endpoint, API-key path, adapter, `SourceSpec`, route, dependency, fixture, or workflow exists |
| Proposed `source_name` | None; rejected before design |
| Proposed adapter path | None; rejected before design |
| Routing surfaces | None; no registry, spec, tier, market-window, segment, config, diagnostics, fixture, secret, dependency, or workflow change |
| Degradation behavior | Not applicable; no runtime path is registered |

## Dated Primary-Source Evidence

Checked on 2026-07-21:

1. `https://financialdata.net/documentation`
   - labels ETF Prices as a Premium subscription endpoint;
   - documents `GET /api/v1/etf-prices?identifier=SPY`, more than ten years of
     end-of-day ETF prices and volumes, and a 300-record response limit;
   - returns `trading_symbol`, `date`, `open`, `high`, `low`, `close`, and `volume`;
   - requires a query-string API key and supports offset pagination plus JSON/CSV;
   - separately labels company Stock Prices as Free, so that route is not evidence
     that ETF price history is free.
2. `https://financialdata.net/pricing`
   - prices Personal Premium at USD 69/month or USD 599/year and includes ETF Data;
   - limits the USD 0 Free plan to 300 requests/day, symbol lists, and market or
     miscellaneous data; the endpoint matrix does not include ETF Prices on Free;
   - prices Enterprise at USD 299/month or USD 2,599/year and is the only listed
     tier with External Commercial Use and Data Display & Redistribution;
   - describes end-of-day stock and ETF coverage since 2015 with daily updates.
3. `https://financialdata.net/terms-of-service`
   - identifies Afinec, SP as the service operator and was last revised 2024-12-10;
   - prohibits copying, aggregation, republication, public display, transmission,
     and distribution unless the terms or applicable subscription permit it;
   - grants redistribution only when the subscription explicitly permits it and
     directs other public-display requests to the provider;
   - requires attribution if separate public-display permission is granted.
4. `https://financialdata.net/stock-prices-api`
   - describes the free company Stock Prices product, which does not replace the
     separately documented Premium ETF Prices route required by u140.

The technical shape is a close fit, but both binding business gates fail. Paying for
Premium would solve endpoint access but still would not provide the Enterprise-only
external display and redistribution entitlement. u140 cannot treat publication of
returns, ranks, volume scores, volatility, and regime labels as free merely because
they are derived from provider rows; the reviewed public terms contain no such grant.

## Deduplication Evidence

A repository scan across `src/`, `tests/`, `scripts/`, `.github/`, and dependency
configuration found no `financialdata.net`, FinancialData.Net API key, `etf-prices`
endpoint, adapter, registry entry, `SourceSpec`, route, fixture, dependency, secret,
or workflow. Adding the source would create a new paid account/key, licensing, and
external-service boundary.

## Gate Decision

| Binding gate | Result | Reason |
| --- | --- | --- |
| Official terms and public derived-display rights | Fail | Public display/distribution requires an expressly permitting subscription, and the pricing page reserves Data Display & Redistribution for paid Enterprise |
| Free access for 63+ daily OHLCV bars | Fail | More than ten years and 300 rows are available only through the paid Premium ETF Prices route |
| Exact 12-symbol coverage and freshness | Not run / unproven | SPY is documented, but exact universe availability and at-most-36-hour publication were not probed after the binding failures |
| Five bounded GitHub Actions probes | Not run | A paid account/key and payload access are unjustified after Step 0 rejection |
| No paid plan/trial/secret exposure | Fail on cost; auth unprobed | Required ETF history starts at Premium; no account, payment method, or key was created |
| Public/raw retention contract | Unproven | No free public caching/retention grant was found; no raw payload was retained |

**Disposition: `reject under current published pricing and terms`.** Reconsider only
if FinancialData.Net makes the exact ETF Prices endpoint permanently free and grants
zero-cost written permission for GitHub Actions processing, bounded cache/fixture
retention, and public display of Investo's numeric derived radar outputs. No account,
key, payment, API request, local probe, GitHub Actions probe, adapter, fixture, public
output, or TECH-DEBT item is created.
