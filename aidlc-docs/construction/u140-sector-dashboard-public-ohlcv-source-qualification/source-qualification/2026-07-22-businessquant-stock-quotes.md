# u140 Source Fact Sheet — BusinessQuant Stock Quotes API

**Checked**: 2026-07-22
**Candidate**: BusinessQuant Stock Quotes API
**Disposition**: Reject under current published terms and pricing
**Probe status**: No account, API key, endpoint request, or provider payload; only public documentation, pricing, and terms were inspected at Step 0

## Source Facts

| Field | Value |
| --- | --- |
| Source owner | Business Quant, the operator identified by the official Terms and privacy contact |
| Data family | Historical EOD, live-merged daily, and intraday one-minute US-listed equity/ETF OHLCV |
| Official docs | `https://businessquant.com/docs/api/quotes`, `https://businessquant.com/docs/api/universe`, `https://businessquant.com/pricing`, and `https://businessquant.com/terms-of-use` |
| Endpoint | `GET https://data.businessquant.com/quotes?ticker={ticker}&mode={mode}&api_key={api_key}` |
| Auth | Required account-issued API key passed as a URL query parameter |
| Cost and no-paid evidence | Quotes docs call the API free. The Free plan is USD 0, needs no credit card, and includes 30 API calls/day plus 0.1 GB transfer/month. Public-use rights do not accompany that technical access. |
| Rate and request budget | Free permits 30 calls/day and the comparison table shows two simultaneous tickers. Six two-ticker calls could cover 12 symbols within the daily count, subject to payload-size and exact-symbol checks that were not run. |
| Format | REST response documented as per-ticker metadata and OHLCV data blocks; JSON examples are shown |
| Key fields | `date`, `open`, `high`, `low`, `close`, and `volume`; metadata includes ticker, date bounds, and pagination |
| Required symbols | Documentation covers US-listed equities and ETFs and the universe endpoint includes ETFs. Exact SPY, XLB, XLC, XLE, XLF, XLI, XLK, XLP, XLRE, XLU, XLV, and XLY availability was not probed because the rights gate failed first. |
| Update cadence | EOD records are documented as finalized after market close, typically within minutes of the 16:00 ET close; `daily` can inject a current live bar |
| Historical range | EOD history is documented as extending back many years for actively traded large caps and ETFs, preliminarily exceeding the 63-trading-day minimum; exact per-symbol depth was not probed |
| Adjustment semantics | No adjusted-close, split-factor, dividend, or explicit split/dividend-adjustment contract was found in the reviewed Quotes fields. A separate Dividends API is suggested for yield-adjusted returns. |
| Venue/volume semantics | `volume` is described as shares traded during the interval, but the reviewed docs do not identify consolidated-tape versus venue-limited provenance. Total-market volume semantics remain unproven. |
| Attribution | No attribution rule that grants free public display was found |
| Caching and raw retention | No free-tier grant for caching, retention, republication, or distribution was found; the general Terms grant no license in accessed data |
| License/public display | Binding Terms say use of the Website gives no ownership or license in content, information, or data, including third-party data. Pricing separately advertises `Commercial use API` for Enterprise and includes commercial redistribution in its plan comparison. Free public derived-display rights are not explicit. |
| Existing Investo overlap | No BusinessQuant endpoint, API-key path, adapter, `SourceSpec`, registry, route, fixture, dependency, or workflow exists |
| Proposed `source_name` | None; rejected before runtime design |
| Proposed adapter path | None; rejected before runtime design |
| Routing surfaces | None; no registry, tier, market window, segment route, secret, dependency, fixture, or workflow change |
| Degradation behavior | Not applicable while rejected; no account or payload behavior was tested |

## Dated Primary-Source Evidence

Checked on 2026-07-22:

1. `https://businessquant.com/docs/api/quotes`
   - last updated 2026-05-17 and advertises free authenticated EOD, daily, and
     minute OHLCV through one endpoint;
   - documents multi-ticker output, date filters, pagination, US-listed equity/ETF
     coverage, many years of EOD history, and end-of-day processing typically within
     minutes of the 16:00 ET close;
   - exposes OHLCV fields but no explicit adjusted-price or consolidated-volume
     contract on the reviewed page.
2. `https://businessquant.com/docs/api/universe`
   - documents an authenticated inventory containing equities, ETFs, and funds;
   - requires an API key to enumerate the production universe, so exact 12-symbol
     coverage was not tested after the rights failure.
3. `https://businessquant.com/pricing`
   - publishes a USD 0 Free plan with no credit card, 30 API calls/day, 0.1 GB/month,
     and two simultaneous tickers;
   - markets `Commercial use API` on Enterprise and treats commercial redistribution
     as a plan-controlled comparison feature rather than a free entitlement.
4. `https://businessquant.com/terms-of-use`
   - binds Website and accessed-data use to the Terms;
   - states that use grants no ownership or license in any accessed content,
     information, or data, including data obtained from third parties;
   - supplies no separate exception for free public numeric derived displays.

The technical documentation is strong enough for a later recheck if BusinessQuant
publishes a free public-display license. It is not sufficient to infer that a free API
key authorizes Investo to publish provider-derived sector metrics on GitHub Pages.
The explicit rights gate fails before account creation, universe enumeration, or
payload inspection.

## Deduplication Evidence

A repository scan across AIDLC docs, runtime, configuration, tests, scripts,
workflows, dependencies, and source-planning surfaces found no `businessquant`,
`data.businessquant.com`, API-key path, quotes endpoint, adapter, registry entry,
`SourceSpec`, route, fixture, dependency, secret, or workflow. No provider data was
requested, copied, or retained.

## Gate Decision

| Binding gate | Result | Reason |
| --- | --- | --- |
| Official terms and public derived-display rights | Fail | Terms grant no license in accessed data; free public derived display is not stated, while commercial use/redistribution is plan-controlled |
| Free access for 63+ daily OHLCV bars | Preliminary technical pass | Free Quotes access and many years of EOD history are documented, but exact rows were not probed |
| Exact 12-symbol coverage | Unproven | ETF-family coverage is documented; the authenticated universe was not queried after the rights failure |
| At-most-36-hour freshness | Preliminary documentation pass | EOD finalization is described as minutes after close; payload behavior remains unprobed |
| Truthful volume/price semantics | Unproven | Adjustment and consolidated-volume provenance are not specified on the reviewed Quotes page |
| Five bounded GitHub Actions probes | Not run | Rights failure blocks Step 1 and Step 2 |
| No paid plan/trial/secret exposure | Pass on technical access only | Free account/API quota exists, but no account or key was created |
| Public/raw retention contract | Fail | No free caching, retention, or public-distribution license was found |

**Disposition: `reject under current published terms and pricing`.** Reconsider only
if official terms expressly authorize free public derived display, caching, and the
intended non-secret output. Then repeat Step 0 and verify exact symbols, adjustment,
volume provenance, continuity, request size, and freshness before any runner probe.
No account, key, payload, fixture, adapter, public output, GitHub Actions probe, or
TECH-DEBT item is created.
