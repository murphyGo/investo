# u140 Source Fact Sheet — Intrinio EOD Historical Stock Prices

**Checked**: 2026-07-21
**Candidate**: Intrinio EOD Historical Stock Prices / Stock Prices by Security API
**Disposition**: Reject under current published pricing and terms for public Pages
**Probe status**: Not run; the candidate failed the permanent-free and explicit free public derived-display gates first

## Source Facts

| Field | Value |
| --- | --- |
| Source owner | Intrinio, with EOD data sourced from all US stock exchanges |
| Data family | End-of-day and historical US equity/ETF prices |
| Official docs | `https://docs.intrinio.com/documentation/web_api/get_security_stock_prices_v2` |
| Endpoint | `GET https://api-v2.intrinio.com/securities/{identifier}/prices` with bounded `start_date`, `end_date`, `frequency=daily`, `page_size`, and pagination token |
| Auth | HTTPS Basic Authentication under an Intrinio account; a credentialed subscription is required for production data access |
| Cost and no-paid evidence | Intrinio publishes a free trial, not a permanent free production tier. Individual access is USD 150/month. Startup display/commercial access begins at USD 333/month, rises after six and twelve months, and is billed quarterly. |
| Rate and request budget | Limits are plan- and Order-Form-specific. Historical stock prices return up to 100 daily rows per page; one page counts as one API call, so a 63-bar request would preliminarily fit in one call per symbol. Exact subscribed limits were not obtained after the cost failure. |
| Format | REST/HTTPS with JSON responses; official SDKs also exist |
| Key fields | `date`, `intraperiod`, `frequency`, `open`, `high`, `low`, `close`, `volume`, `adj_open`, `adj_high`, `adj_low`, `adj_close`, `adj_volume`, `factor`, `split_ratio`, and `dividend` |
| Required symbols | The endpoint accepts a ticker or other security identifier and the feed advertises full US exchange coverage, making XLK/XLC/XLY/XLP/XLE/XLF/XLV/XLI/XLB/XLRE/XLU/SPY plausible; exact 12-symbol results were not probed after binding gate failures |
| Update cadence | The EOD historical product is advertised as updating daily. Exact at-most-36-hour availability for the 12-symbol universe was not probed. |
| Historical range | More than 50 years are advertised, which preliminarily clears the 63-trading-day requirement |
| Adjustment semantics | Raw and split/dividend-adjusted OHLCV are separate fields, with adjustment factor, split ratio, and dividend amount exposed for an explicit adapter contract |
| Attribution | No reviewed public page offers an attribution-only exception that creates free public display rights |
| Caching and raw retention | Ordinary rights are internal only unless an executed Order Form says otherwise. No public raw-retention or redistribution grant was established for Investo. |
| License/public display | The Individual plan expressly says no redistribution or external display. Current terms define any third-party website/dashboard/report presentation as Display and require rights in an executed Order Form; display/commercial rights are generally available only on paid Startup or Enterprise plans. Externally visible aggregated, transformed, derived, or AI-generated output is not presumed exempt. |
| Existing Investo overlap | No Intrinio endpoint, credential path, adapter, `SourceSpec`, route, dependency, fixture, or workflow exists |
| Proposed `source_name` | None; rejected before design |
| Proposed adapter path | None; rejected before design |
| Routing surfaces | None; no registry, spec, tier, market-window, segment, config, diagnostics, fixture, secret, dependency, or workflow change |
| Degradation behavior | Not applicable; no runtime path is registered |

## Dated Primary-Source Evidence

Checked on 2026-07-21:

1. `https://docs.intrinio.com/documentation/web_api/get_security_stock_prices_v2`
   - documents the per-security EOD endpoint, ticker/identifier lookup, bounded
     dates, daily frequency, page size, and pagination;
   - returns raw and adjusted OHLCV plus factor, split, dividend, and security
     identity fields.
2. `https://intrinio.com/access-methods`
   - documents RESTful HTTPS Web API access, Basic Authentication, JSON responses,
     and official SDK availability;
   - identifies the Web API as the normal EOD and historical access path.
3. `https://help.intrinio.com/whats-an-api-call-and-how-are-they-counted`
   - states that historical stock-price pages can contain up to 100 daily rows;
   - counts each page as one API call and confirms raw and adjusted OHLCV within a
     historical price page.
4. `https://intrinio.com/pricing`
   - prices Individual production access at USD 150/month and explicitly excludes
     redistribution or external display;
   - prices Startup at USD 333/month to start, includes Display & Commercial Use,
     and advertises only a free trial rather than a permanent free tier;
   - advertises 50+ years of daily full-volume US EOD history with raw/adjusted
     prices, volume, adjustment factors, and split ratios.
5. `https://about.intrinio.com/terms`
   - effective 2026-06-03, defines Display to include websites, applications,
     dashboards, APIs, portals, and reports visible to any third party;
   - limits access to internal purposes unless an executed Order Form grants more
     and says Display/redistribution rights are generally only available under
     Startup or Enterprise plans;
   - treats externally visible transformed, aggregated, derived, or AI-assisted
     output as requiring applicable external-display rights rather than granting a
     free derived-data exemption.

The API is technically well matched to u140: a 63-day daily response fits in one
page per ticker, adjustment semantics are explicit, and 50+ years of US EOD history
are advertised. The commercial and rights gates are decisive. Production data is
paid, the lowest published plan is internal-only, and public display requires a paid
plan plus an executed Order Form.

## Deduplication Evidence

A repository scan across `src/`, `tests/`, `scripts/`, `.github/`, `CONTRIBUTING.md`,
dependency configuration, AIDLC plans, requirements, and session docs found no
`intrinio`, `api-v2.intrinio.com`, `INTRINIO_API_KEY`, stock-price endpoint, adapter,
registry entry, `SourceSpec`, route, fixture, dependency, secret, or workflow. Adding
the source would create a new paid external dependency, credential boundary, and
licensed-display contract.

## Gate Decision

| Binding gate | Result | Reason |
| --- | --- | --- |
| Official terms and public derived-display rights | Fail | Individual explicitly forbids external display; third-party display and externally visible derived output require a paid plan and executed Order Form |
| Free access for 63+ daily OHLCV bars | Fail | Only a trial is free; production Individual access is USD 150/month |
| Exact 12-symbol coverage and freshness | Not run | Fail-fast after binding cost and rights failures; exact rows, continuity, and at-most-36-hour availability remain unproven |
| Five bounded GitHub Actions probes | Not run | A paid subscription/account and credentials are prohibited after Step 0 rejection |
| No paid plan/trial/secret exposure | Fail | Production requires a paid subscription and authenticated account |
| Public/raw retention contract | Fail / unproven | Internal-use rights do not authorize public raw retention, publication, or redistribution |

**Disposition: `reject under current published pricing and terms`.** Reconsider only
if Intrinio publishes or executes a perpetual zero-cost production grant sufficient
for the daily 12-symbol workload and expressly permits Investo's derived metrics,
caching, raw retention, GitHub Actions processing, and GitHub Pages display. No
account, free-trial enrollment, paid-plan inquiry, credentialed request, local probe,
GitHub Actions probe, adapter, fixture, public output, or TECH-DEBT item is created.
