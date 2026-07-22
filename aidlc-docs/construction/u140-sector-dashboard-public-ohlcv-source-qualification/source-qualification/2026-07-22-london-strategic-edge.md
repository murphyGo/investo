# u140 Source Fact Sheet — London Strategic Edge Free Market Data API

**Checked**: 2026-07-22
**Candidate**: London Strategic Edge Free Market Data API
**Disposition**: Reject under current published terms
**Probe status**: No account, API key, endpoint request, or provider payload; only public product pages and binding Terms were inspected at Step 0

## Source Facts

| Field | Value |
| --- | --- |
| Source owner | Platform and Terms operator named London Strategic Edge; the reviewed static terms do not identify a separate registered data-owning entity |
| Data family | Historical and live OHLCV for stocks, ETFs, forex, crypto, commodities, and indices |
| Official docs | `https://londonstrategicedge.com/free-market-data-api/`, `https://londonstrategicedge.com/api/`, `https://londonstrategicedge.com/data/`, and `https://londonstrategicedge.com/terms-of-service` |
| Endpoint | Plain-HTTP candle grammar is documented through the dynamic `/docs/api` reference and official `lse-data` client; the stable raw REST path was not exposed on the reviewed static page. The client example is `client.candles(instrument, resolution, start=...)`. |
| Auth | One free account-issued API key for REST and WebSocket access |
| Cost and no-paid evidence | Official pages describe the API as free with no tiers or credit card. Free API access does not include a public redistribution or derived-display grant. |
| Rate and request budget | Candle requests return up to 5,000 rows and longer histories paginate. The databank advertises ten downloads/hour at up to one million rows, but a binding REST request-rate limit was not found on the reviewed static pages. |
| Format | JSON or CSV for API responses; Parquet or CSV for databank downloads |
| Key fields | OHLCV candles at one-minute, five-minute, 15-minute, one-hour, four-hour, and daily resolutions |
| Required symbols | The provider advertises 25 index and sector ETFs. Exact SPY, XLB, XLC, XLE, XLF, XLI, XLK, XLP, XLRE, XLU, XLV, and XLY coverage was not verified because rights failed first. |
| Update cadence | A live WebSocket and historical HTTP path are advertised. No binding EOD publication deadline or at-most-36-hour daily freshness contract was found. |
| Historical range | Daily candles are advertised back to 2003 for long-listed instruments, well beyond 63 trading days where a required ticker is covered |
| Adjustment semantics | Dividends and stock splits are separate data families, but the reviewed candle page does not state whether OHLC is raw, split-adjusted, or dividend-adjusted |
| Venue/volume semantics | No reviewed official page identifies the upstream ETF market-data vendor, exchange/SIP scope, or whether volume is consolidated or venue-limited |
| Attribution | No attribution-based exception to the redistribution prohibition was found |
| Caching and raw retention | No free public retention grant was found. Terms prohibit redistribution and copying/modifying/distributing data compilations without express written consent. |
| License/public display | Terms prohibit redistribution, resale, or commercial exploitation of data/services and prohibit copying, modifying, distributing, or creating derivative works without express written consent. This fails Investo's free public derived-display gate. |
| Existing Investo overlap | No London Strategic Edge endpoint, `lse-data` client, API-key path, adapter, `SourceSpec`, registry, route, fixture, dependency, or workflow exists |
| Proposed `source_name` | None; rejected before runtime design |
| Proposed adapter path | None; rejected before runtime design |
| Routing surfaces | None; no registry, tier, market window, segment route, config, secret, dependency, fixture, or workflow change |
| Degradation behavior | Not applicable while rejected; account, auth, quota, malformed payload, and outage behavior were not probed |

## Dated Primary-Source Evidence

Checked on 2026-07-22:

1. `https://londonstrategicedge.com/free-market-data-api/`
   - updated 2026-06-11 and advertises one free key, plain-HTTP historical data,
     daily through one-minute OHLCV, JSON/CSV, and up to 5,000 rows per request;
   - claims 25 index/sector ETFs and daily history back to 2003 for long-listed
     instruments;
   - points to a JavaScript-dependent API reference and the `lse-data` client but
     does not expose a static exact-ticker inventory or upstream market-data source.
2. `https://londonstrategicedge.com/api/`
   - advertises the candle client grammar, date windows, pagination, ETF coverage,
     and JSON/CSV output;
   - says the allowance is shared with streaming but does not publish a binding
     REST request-rate contract on the reviewed static page.
3. `https://londonstrategicedge.com/data/`
   - advertises 25 ETFs, Parquet/CSV downloads, ten free downloads per hour, and up
     to one million rows per databank download;
   - does not supply public reuse rights or exact required-ticker evidence.
4. `https://londonstrategicedge.com/terms-of-service`
   - last updated 2026-01-19 and governs the platform, API services, and market data;
   - prohibits extraction or automated access without permission and prohibits
     redistribution, resale, or commercial exploitation of data/services;
   - prohibits copying, modifying, distributing, or creating derivative works from
     protected platform content and data compilations without express written consent.

The documented API is an intended automated-access surface, but that does not override
the separate public redistribution and derivative-work restrictions. Investo has no
written consent. Publishing provider-derived returns, volume, volatility, and regime
metrics on public Pages therefore cannot be inferred from free account access.

## Deduplication Evidence

A repository scan across AIDLC docs, runtime, configuration, tests, scripts,
workflows, dependencies, and source-planning surfaces found no
`londonstrategicedge`, `lse-data`, API-key path, candle endpoint/client, adapter,
registry entry, `SourceSpec`, route, fixture, dependency, secret, or workflow. No
provider data was requested, copied, or retained.

## Gate Decision

| Binding gate | Result | Reason |
| --- | --- | --- |
| Official terms and public derived-display rights | Fail | Terms prohibit redistribution and derivative works without express written consent |
| Free access for 63+ daily OHLCV bars | Preliminary technical pass | Free daily candles and history to 2003 are advertised for long-listed covered instruments |
| Exact 12-symbol coverage | Unproven | Only aggregate 25-ETF coverage is public on the reviewed page; no account or payload was requested |
| At-most-36-hour freshness | Unproven | Live streaming is advertised, but no binding daily finalization deadline was found |
| Truthful volume/price semantics | Unproven | Adjustment and upstream/consolidated-volume provenance are undocumented on the reviewed pages |
| Five bounded GitHub Actions probes | Not run | Rights failure blocks Step 1 and Step 2 |
| No paid plan/trial/secret exposure | Pass on technical access only | One free key/no tiers are advertised, but no account or key was created |
| Public/raw retention contract | Fail | No free retention/distribution grant exists; express written consent is required for copying/distribution/derivatives |

**Disposition: `reject under current published terms`.** Reconsider only if the
provider grants Investo written public derived-display and retention permission and
publishes upstream ETF-price/volume provenance. Then repeat Step 0 and verify the
exact universe, endpoint grammar, adjustment, continuity, freshness, and request
limits before any runner probe. No account, key, payload, fixture, adapter, public
output, GitHub Actions probe, or TECH-DEBT item is created.
