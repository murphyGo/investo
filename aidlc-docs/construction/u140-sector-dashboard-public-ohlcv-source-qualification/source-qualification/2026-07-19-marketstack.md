# u140 Source Fact Sheet — Marketstack EOD API

**Checked**: 2026-07-19
**Candidate**: Marketstack v2 end-of-day API
**Disposition**: Reject under current written terms for public Pages
**Probe status**: Not run; the candidate failed the free public-rights gate first

## Source Facts

| Field | Value |
| --- | --- |
| Source owner | APILayer / Idera, operating Marketstack; US market data is described as licensed from Tiingo |
| Data family | Historical global end-of-day price and volume data |
| Official docs | `https://docs.apilayer.com/marketstack/docs/api-endpoints-v2` and the linked official OpenAPI specification |
| Endpoint | `GET https://api.marketstack.com/v2/eod` with required comma-separated `symbols`, optional exchange/date/sort/pagination parameters, and query authentication |
| Auth | Required `access_key` query parameter |
| Cost and no-paid evidence | Free is USD 0/month with 100 requests/month, EOD data, one year of history, splits, and dividends; Commercial Use first appears on paid Basic at USD 9.99/month |
| Request budget | 100 requests/month; a single `/eod` call accepts multiple comma-separated symbols, so one daily 12-symbol batch is technically within budget |
| Format | JSON with pagination |
| Key fields | Date, symbol, name, exchange/MIC, asset type, currency, raw open/high/low/close/volume, adjusted open/high/low/close/volume, split factor, and dividend |
| Required symbols | `XLC, XLY, XLP, XLE, XLF, XLV, XLI, XLB, XLRE, XLK, XLU, SPY`; documented US exchange and multi-symbol coverage makes the universe plausible, but exact rows were not probed after rejection |
| Update cadence | End-of-day; precise weekday publication time was not established before the rights failure |
| Historical range | One year on Free, sufficient in principle for the 63-bar minimum |
| Adjustment semantics | OpenAPI states adjusted fields account for splits and dividends using CRSP methodology; raw and adjusted OHLCV plus split/dividend fields are distinct |
| Attribution | No free public-display contract or attribution rule that authorizes Investo Pages was established |
| Caching and raw retention | No public retention grant was established; no Marketstack payload or fixture is stored |
| License/public display | Free pricing omits Commercial Use, which begins on paid Basic. The current APILayer legal agreement linked by Marketstack limits Freeware to testing/evaluation and does not grant free public derived-display or redistribution rights. |
| Existing Investo overlap | No Marketstack/APILayer runtime, test, config, dependency, or workflow surface exists. Existing Yahoo history/u138 remains operational evidence only and does not supply Marketstack rights. |
| Proposed `source_name` | None; rejected before design |
| Proposed adapter path | None; rejected before design |
| Routing surfaces | None; no registry, spec, tier, market-window, segment, config, diagnostics, fixture, key, or workflow change |
| Degradation behavior | Not applicable; no runtime path is registered |

## Dated Primary-Source Evidence

Checked on 2026-07-19:

1. `https://docs.apilayer.com/marketstack/docs/api-endpoints-v2` and
   `https://api.swaggerhub.com/apis/apilayer-863/MarketstackAPIv2/2.0.0/swagger.json`
   - document the `https://api.marketstack.com/v2` base URL, required `access_key`,
     and `/eod` with one or multiple comma-separated symbols;
   - define raw and adjusted OHLCV, dividend, split factor, identity, exchange,
     currency, asset-type, and timezone-bearing date fields;
   - describe CRSP-style split/dividend adjustments.
2. `https://marketstack.com/pricing/`
   - lists Free at 100 requests/month, EOD data, one year of history, splits, and
     dividends;
   - omits Commercial Use from Free and includes it beginning with paid Basic at
     USD 9.99/month;
   - identifies US exchange data as licensed from Tiingo.
3. `https://www.ideracorp.com/legal/APILayer` and its linked Master SaaS Subscription
   Agreement
   - are the current legal surfaces linked from Marketstack;
   - define Freeware as no-charge access for limited purposes and license it solely
     for the customer's testing and evaluation;
   - do not provide a free public display, derived-display, or redistribution grant.

The technical request budget is viable because all 12 symbols fit one documented
batch and one year exceeds 63 trading bars. That does not clear the binding rights
gate. Investo does not infer public derived-display permission from API availability
when the free plan excludes Commercial Use and the linked free license is confined
to testing/evaluation.

## Deduplication Evidence

A repository scan across `src/`, `tests/`, `scripts/`, `.github/`, `CONTRIBUTING.md`,
dependency configuration, AIDLC plans, and requirements found no Marketstack or
APILayer adapter, registration, source spec, tier/window/segment route, fixture,
credential, dependency, or workflow. Adding it would introduce a new query-key trust
boundary and would still leave the public rights gate unresolved.

## Gate Decision

| Binding gate | Result | Reason |
| --- | --- | --- |
| Official terms and public derived-display rights | Fail | Freeware is limited to testing/evaluation; no public display or redistribution grant |
| Free access for 63+ daily OHLCV bars | Preliminary pass | Free provides one year of multi-symbol EOD raw/adjusted OHLCV at 100 requests/month |
| Exact 12-symbol coverage and freshness | Not run | Fail-fast after the binding rights failure |
| Five bounded GitHub Actions probes | Not run | A new key and provider-payload testing are unjustified after rejection |
| No paid plan/trial/secret exposure | Fail for public use | Commercial Use begins on paid Basic; API access also requires a key |
| Public/raw retention contract | Not established | No free public-use grant; no payload retained |

**Disposition: `reject under current written terms`.** Reconsider only if APILayer
provides a free written license that explicitly covers Investo's public derived
fields, attribution, caching, raw-retention policy, and GitHub Pages delivery. No
account/key, local probe, GitHub Actions probe, adapter, fixture, Pages output, or
TECH-DEBT item is created.
