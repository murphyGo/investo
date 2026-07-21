# u140 Source Fact Sheet — SimFin Daily Share Prices

**Checked**: 2026-07-21
**Candidate**: SimFin Daily Share Prices through the Data API / bulk-download path
**Disposition**: Reject under the current FREE/BASIC data license for public Pages
**Probe status**: Not run; explicit free public derived-display rights failed before account or payload access

## Source Facts

| Field | Value |
| --- | --- |
| Source owner | SimFin Analytics GmbH |
| Data family | Daily share prices for SimFin's covered US-company universe |
| Official docs | `https://www.simfin.com/en/prices/`, `https://github.com/SimFin/simfin`, and `https://www.simfin.com/en/technical-updates-to-api-v3-and-bulk-download/` |
| Endpoint | Official Python path `load_shareprices(market="us", variant="daily")`, which downloads share-price data from SimFin; the current backend is `https://prod.simfin.com`, and official update notes refer to the API v3 `/prices` family. The exact direct-HTTP route was not fixed after the rights failure. |
| Auth | A SimFin account API key is required; the official repository says a key can be obtained free after registration |
| Cost and no-paid evidence | The FREE plan is USD 0 with no billing and includes Data API/bulk download plus five years of chart history. This provisionally clears the durable no-paid and 63-bar depth gates while the account remains active. |
| Rate and request budget | The pricing comparison publishes a two-request-per-second Free Web API limit and 500 monthly high-speed credits. The daily-share-price loader is a dataset download path rather than a documented 12-single-symbol request contract; exact request accounting was not probed. |
| Format | Python/Pandas dataset, CSV bulk download, and JSON Web API surfaces are advertised |
| Key fields | Official pricing lists daily opening, closing, highest, lowest, adjusted closing price, and trading volume; official Python examples load daily share prices and index by ticker/date |
| Required symbols | SimFin advertises about 5,000 US stocks/companies, but does not expressly promise the 11 SPDR sector ETFs plus SPY on the reviewed pages. Exact ETF coverage remains unproven. |
| Update cadence | Daily prices are advertised. The Free bulk-history row is labeled `5 Years (delayed)` without defining the delay on the reviewed public page, so the at-most-36-hour weekday freshness gate remains unproven. |
| Historical range | Five years on Free, preliminarily more than the required 63 trading days |
| Adjustment semantics | Separate close and adjusted close are published. Split/dividend factor and adjusted-volume semantics were not established from the reviewed public contract. |
| Attribution | No attribution-only clause overrides the FREE/BASIC own-use and no-sharing restriction |
| Caching and raw retention | Pricing states downloaded data must be deleted, including backups, when the subscription ends; the license term ends with the subscription period. This does not support indefinite public-repository raw retention. |
| License/public display | FREE/BASIC grants personal-research own use only and prohibits sharing, copying, distribution, transfer, or making data available to other parties. Reprocessed data retains the same confidentiality/use/disclosure/transfer limits. Redistribution is a separate commercial license, and SimFin says Enterprise is the only subscription allowing redistribution. The license says `interpretations` are unrestricted but does not define public numeric transformed metrics as interpretations; u140 cannot infer that its returns, ranks, volume scores, and regimes fall outside restricted reprocessed data. |
| Existing Investo overlap | No SimFin endpoint, API-key path, adapter, `SourceSpec`, route, dependency, fixture, or workflow exists |
| Proposed `source_name` | None; rejected before design |
| Proposed adapter path | None; rejected before design |
| Routing surfaces | None; no registry, spec, tier, market-window, segment, config, diagnostics, fixture, secret, dependency, or workflow change |
| Degradation behavior | Not applicable; no runtime path is registered |

## Dated Primary-Source Evidence

Checked on 2026-07-21:

1. `https://www.simfin.com/en/prices/`
   - publishes a USD 0 Free account with no billing, five years of chart history,
     Data API and bulk download, daily OHLC, adjusted close, and volume;
   - lists a two-request-per-second Free Web API limit and labels the five-year Free
     bulk history `delayed` without defining the delay;
   - requires deletion of downloaded data and backups when a subscription ends and
     routes commercial projects to an individually quoted Enterprise plan.
2. `https://www.simfin.com/en/commercial-license/`
   - defines FREE/BASIC as personal-research own use and prohibits sharing or making
     the data available to other parties;
   - keeps reprocessed data under the original confidentiality, use, disclosure, and
     transfer restrictions;
   - creates a separate redistribution license. Its `interpretations` exception is
     undefined and does not expressly grant public display of numeric transformed
     datasets or dashboards.
3. `https://www.simfin.com/en/fundamental-data-download/`
   - states that Enterprise is the only subscription permitting redistribution of
     downloaded SimFin data;
   - repeats the deletion requirement after a Data API subscription ends.
4. `https://github.com/SimFin/simfin`
   - is SimFin's official Python repository and requires an API key obtainable after
     free registration;
   - demonstrates `load_shareprices(market="us", variant="daily")` and local caching
     of downloaded datasets.
5. `https://www.simfin.com/en/technical-updates-to-api-v3-and-bulk-download/`
   - identifies the API v3 `/prices` family and current `prod.simfin.com` backend;
   - documents date-string output and `start_date`/`end_date` filtering for the
     share-price dataset.

Cost, history depth, and advertised fields are technically promising. Rights are not.
The product's public dashboard would expose quantitative returns, ranks, volume
signals, volatility, and regime labels derived from SimFin rows. The license expressly
keeps reprocessed data restricted, and the undefined interpretations exception is not
sufficient evidence that these numeric outputs may be published. Exact ETF coverage
and freshness are also not established.

## Deduplication Evidence

A repository scan across `src/`, `tests/`, `scripts/`, `.github/`, `CONTRIBUTING.md`,
dependency configuration, AIDLC plans, requirements, and session docs found no
`simfin`, `prod.simfin.com`, `SIMFIN_API_KEY`, `load_shareprices`, share-price adapter,
registry entry, `SourceSpec`, route, fixture, dependency, secret, or workflow. Adding
the source would create a new account/key, external dataset, bulk-cache, and licensing
boundary.

## Gate Decision

| Binding gate | Result | Reason |
| --- | --- | --- |
| Official terms and public derived-display rights | Fail | FREE/BASIC forbids sharing and restricts reprocessed data; the interpretations exception does not expressly authorize public numeric radar output |
| Free access for 63+ daily OHLCV bars | Preliminary pass | Free advertises five years, daily OHLC/adjusted close/volume, API/bulk access, and no billing |
| Exact 12-symbol coverage and freshness | Not run / unproven | Reviewed pages do not promise ETF coverage or define the Free `delayed` period; fail-fast after the rights failure |
| Five bounded GitHub Actions probes | Not run | Creating an account/key and retaining payloads is unjustified after the binding rights rejection |
| No paid plan/trial/secret exposure | Preliminary pass on cost; auth unprobed | Free has no billing but requires an account API key; no credential was created or stored |
| Public/raw retention contract | Fail | Data must remain own-use and downloaded copies/backups must be deleted when the subscription ends |

**Disposition: `reject under the current FREE/BASIC data license`.** Reconsider only
if SimFin publishes or executes a zero-cost written grant that classifies Investo's
numeric return, volume, volatility, ranking, and regime outputs as publicly displayable
derived interpretations; permits GitHub Actions processing, cache/fixture retention,
and GitHub Pages publication; and confirms the exact 12 ETFs with at-most-36-hour
freshness. No account, key, API/bulk request, local probe, GitHub Actions probe,
adapter, fixture, public output, or TECH-DEBT item is created.
