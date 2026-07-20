# u140 Source Fact Sheet — Barchart OnDemand getHistory API

**Checked**: 2026-07-21
**Candidate**: Barchart OnDemand `getHistory` API
**Disposition**: Reject under current published terms for public Pages
**Probe status**: Not run; the candidate failed the permanent-free and public-use rights gates first

## Source Facts

| Field | Value |
| --- | --- |
| Source owner | Barchart.com, Inc.; the terms also reserve rights to Barchart's data providers |
| Data family | Historical OHLCV for stocks, ETFs, indexes, mutual funds, futures, FX, cash commodities, and cryptocurrencies |
| Official docs | `https://www.barchart.com/ondemand/api/getHistory` |
| Endpoint | `GET https://ondemand.websol.barchart.com/getHistory.json?apikey={key}&symbol={symbol}&type=daily&startDate={YYYYMMDD}&endDate={YYYYMMDD}&order=asc&splits=true&dividends=true` |
| Auth | A secret API key is required; the official examples pass `apikey` in the request |
| Cost and no-paid evidence | Barchart advertises only a limited-request free trial for evaluation before committing to a plan. OnDemand production pricing is usage-based and tailored from small through enterprise packages; no perpetual zero-cost production tier or quota is published. |
| Rate and request budget | No public production quota or zero-cost request allowance is stated for `getHistory`. The trial is described only as limited requests, so the 12-symbol daily workload has no durable free budget. |
| Format | REST responses are available as JSON, XML, or CSV; the API also documents POST and SOAP examples |
| Key fields | `symbol`, `timestamp`, `tradingDay`, `open`, `high`, `low`, `close`, and `volume` |
| Required symbols | Official coverage includes stocks and ETFs, making the 11 sector ETFs and SPY syntactically plausible; exact entitlements and the 12-symbol result set were not probed after the binding gate failures |
| Update cadence | The product advertises real-time, delayed, end-of-day, and historical data. The free-trial page gives no weekday freshness SLA or entitlement that proves the u140 at-most-36-hour gate. |
| Historical range | `startDate`, `endDate`, and `maxRecords` are supported, and the FAQ says results default to 1,000 records unless a larger maximum is requested. This is technically compatible with 63 bars, but trial history depth for the exact ETF universe is not guaranteed. |
| Adjustment semantics | `splits` and `dividends` apply to stocks and default to true; the fact sheet would pin both explicitly if a licensed candidate advanced |
| Attribution | The general terms allow attributed static screenshots for narrow news, social, or educational uses. That exception does not grant programmatic API redistribution or public derived-display rights. |
| Caching and raw retention | No reviewed public production contract grants Investo public raw caching or retained fixtures. The general terms permit only incidental browser/RAM caching and prohibit broader reproduction or distribution without consent. |
| License/public display | The general terms limit ordinary content use to personal, non-commercial use and prohibit reproduction, publication, broadcast, circulation, or distribution without prior express written consent from Barchart and relevant data providers. Barchart separately identifies websites and data redistributors as exchange-fee subjects and routes website/app use cases to sales pricing. |
| Existing Investo overlap | No Barchart OnDemand adapter, endpoint, key, `SourceSpec`, route, dependency, fixture, or workflow exists. Two Nasdaq news fixtures contain `Barchart` only as an article creator value, not a price-source integration. |
| Proposed `source_name` | None; rejected before design |
| Proposed adapter path | None; rejected before design |
| Routing surfaces | None; no registry, spec, tier, market-window, segment, config, diagnostics, fixture, secret, or workflow change |
| Degradation behavior | Not applicable; no runtime path is registered |

## Dated Primary-Source Evidence

Checked on 2026-07-21:

1. `https://www.barchart.com/ondemand/api/getHistory`
   - documents historical stocks and ETFs with daily data, date bounds, ordering,
     JSON/XML/CSV output, and the API-key parameter;
   - returns OHLCV plus exchange timestamps/trading dates and supports explicit
     split and dividend adjustments.
2. `https://www.barchart.com/ondemand/data`
   - lists ETF and stock price data at delayed, end-of-day, and historical
     frequencies, including daily data.
3. `https://www.barchart.com/solutions/services/ondemand`
   - offers a free trial only to test the API with limited requests before
     committing to a plan;
   - routes data selection and delivery to a solution tailored to the customer's
     workflow, use case, and budget.
4. `https://www.barchart.com/ondemand`
   - states that OnDemand pricing is based on usage and packages are tailored from
     small through enterprise solutions;
   - gives a public website/mobile-app market-data use case as a request for monthly
     pricing rather than a zero-cost entitlement.
5. `https://www.barchart.com/ondemand/faq`
   - identifies `getHistory` as a subscription API and documents the default
     1,000-record response limit.
6. `https://www.barchart.com/solutions/legal/terms`
   - limits ordinary use to personal, non-commercial use and restricts downloaded
     files to personal use;
   - prohibits reproducing, publishing, broadcasting, circulating, or distributing
     content without prior express written consent from Barchart and relevant data
     providers;
   - provides only a narrow attributed-static-screenshot exception, which is not an
     API or derived-data license.
7. `https://www.barchart.com/solutions/exchange-fees`
   - states that redistribution fees apply to websites, data sellers, and entities
     passing data to another person or firm, with licensing coordinated through
     sales.

The endpoint is technically suitable for a 63-bar OHLCV calculation, but the only
published free access is a limited evaluation trial. Production access is usage-based,
and the reviewed terms do not grant a free public derived-display license. That fails
both binding gates before credentials or payloads are justified.

## Deduplication Evidence

A repository scan across `src/`, `tests/`, `scripts/`, `.github/`, `CONTRIBUTING.md`,
dependency configuration, AIDLC plans, and requirements found no OnDemand endpoint,
API key, adapter, registry, spec, route, fixture, or workflow. The string `Barchart`
appears only as publisher metadata in existing Nasdaq/Yahoo news fixtures and tests;
it creates no market-data rights or implementation overlap.

## Gate Decision

| Binding gate | Result | Reason |
| --- | --- | --- |
| Official terms and public derived-display rights | Fail | General terms require prior express written consent for publication/distribution, while the public app/website path is sales-led and no free derived-display grant is published |
| Free access for 63+ daily OHLCV bars | Fail | Only a limited-request evaluation trial is offered; production is usage-priced with no permanent free tier or quota |
| Exact 12-symbol coverage and freshness | Not run | Fail-fast after the cost/rights failures; exact ETF entitlements and at-most-36-hour freshness remain unproven |
| Five bounded GitHub Actions probes | Not run | A trial API key and paid production path are unjustified after rejection |
| No paid plan/trial/secret exposure | Fail | The path depends on a limited trial, then a usage-priced plan, and requires an API key |
| Public/raw retention contract | Fail | No reviewed public contract grants retained raw fixtures or public cached/derived delivery; ordinary terms restrict reproduction and distribution |

**Disposition: `reject under current published terms`.** Reconsider only if Barchart
provides a perpetual zero-cost production entitlement plus written permission covering
Investo's public derived fields, attribution, caching, raw retention, GitHub Actions,
and GitHub Pages, together with any required data-provider or exchange permissions.
No account/key, local probe, GitHub Actions probe, adapter, fixture, Pages output, or
TECH-DEBT item is created.
