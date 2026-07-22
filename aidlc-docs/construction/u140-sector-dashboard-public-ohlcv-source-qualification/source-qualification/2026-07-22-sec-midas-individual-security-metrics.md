# u140 Source Fact Sheet — SEC MIDAS Metrics by Individual Security

**Checked**: 2026-07-22
**Candidate**: SEC MIDAS Market Structure Data, Metrics by Individual Security
**Disposition**: Reject as the u140 public OHLCV source; defer only as a possible Phase 2 market-structure research input
**Probe status**: No ZIP download, extraction, provider payload, fixture, parser, local probe, or GitHub Actions probe; only official SEC catalog, schema, methodology, and FAQ pages were inspected at Step 0

## Source Facts

| Field | Value |
| --- | --- |
| Source owner | U.S. Securities and Exchange Commission |
| Data family | SEC MIDAS Market Activity Data Series aggregated from exchange feeds and related reference inputs |
| Official docs | `https://www.sec.gov/data-research/market-structure-data`, the individual-security download page, Market Activity Report Methodology, and MIDAS FAQ |
| Endpoint/delivery | Anonymous quarterly ZIP downloads from SEC.gov; no API key or account. |
| Auth/contract | None for downloading the published ZIPs. Exact downstream rights were not elevated to an acceptance decision because the OHLC/freshness/volume gates fail first. |
| Cost and no-paid evidence | Pass for access: official files are anonymously downloadable at no charge. |
| Rate and request budget | One quarterly ZIP is roughly 19.5–22.4 MB for recent quarters. This is bounded for occasional research but not a daily publication interface. |
| Format | Quarterly ZIP archives containing individual-security market-activity datasets. |
| Key fields | Ticker, Date, Security, market-cap/turnover/volatility/price ranks, Cancels, Trades, LitTrades, OddLots, Hidden, order/trade volume and lit/odd-lot/hidden volume fields. No Open, High, Low, or Close columns are published. |
| Required symbols | More than 4,800 securities and ETPs are covered, but exact SPY/XLB/XLC/XLE/XLF/XLI/XLK/XLP/XLRE/XLU/XLV/XLY rows were not downloaded because the schema and cadence fail first. |
| Update cadence | Quarterly releases. The current catalog ends at 2025 Q4 / December 2025, far outside the u140 at-most-36-hour requirement on 2026-07-22. |
| Historical range | January 2012 through December 2025 on the current page, far deeper than 63 trading days but stale for a live radar. |
| Adjustment semantics | No daily OHLC or adjusted price series. SEC methodology uses CRSP close/quote midpoint to derive ranks and related measures, but the user-download schema exposes `PriceRank`, not the underlying comparable adjusted close. |
| Venue/volume semantics | MIDAS trade volume reflects available on-exchange continuous-session activity. SEC states it generally excludes off-exchange trading, opening/closing auctions, off-hours trading, and exchanges/days with insufficient feed data. It is not consolidated ETF volume. |
| Attribution | SEC staff methodology and limitations must be preserved if used for later research; no u140 public field is accepted from this candidate. |
| Caching and raw retention | Quarterly public downloads are designed for analysis. No data is downloaded or retained in this decision. |
| License/public display | Not promoted to an accepted u140 grant. Official public availability is favorable, but the dataset cannot reach the product surface because three technical/semantic gates fail first. |
| Existing Investo overlap | Existing SEC adapters collect company facts/submissions for filings and fundamentals. No MIDAS ZIP parser, registry entry, `SourceSpec`, route, fixture, dependency, or workflow exists. |
| Proposed `source_name` | None; rejected before runtime design |
| Proposed adapter path | None; rejected before runtime design |
| Routing surfaces | None; no registry, tier, route, config, dependency, fixture, raw store, workflow, or public output change |
| Degradation behavior | Not applicable while rejected; quarterly publication lag, file revision, missing ticker/day, and methodology changes were not runtime-probed |

## Dated Primary-Source Evidence

Checked on 2026-07-22:

1. `https://www.sec.gov/data-research/market-structure-data`
   - identifies the official market-structure downloads and shows the current
     individual-security series last updated in December 2025.
2. `https://www.sec.gov/data-research/sec-markets-data/marketstructuredata-security`
   - lists January 2012 through December 2025, more than 4,800 securities, the exact
     published columns, quarterly ZIPs, and recent 19.5–22.4 MB file sizes;
   - the schema has ranks/counts/volumes but no OHLC columns.
3. `https://www.sec.gov/featured-topics/market-structure-analytics/market-activity-report-methodology`
   - describes continuous-session filtering, special-trade exclusions, CRSP-based
     price ranks, daily order/trade volume accumulation, and monthly reference lag.
4. `https://www.sec.gov/securities-topics/market-structure-analytics/midas-feedback`
   - explains that MIDAS volume differs from composite volume and generally excludes
     off-exchange activity, opening/closing auctions, off-hours trading, and unavailable
     exchange feeds.

## Deduplication Evidence

A repository scan found no SEC MIDAS download, parser, registry entry, `SourceSpec`,
route, fixture, dependency, secret, or workflow. Existing `sec-company-facts` and SEC
submissions paths provide issuer filings/fundamentals, not market prices. FINRA daily
short-sale volume and SEC Form N-PORT are already separate Phase 2 candidates and do
not duplicate the MIDAS market-activity series.

## Gate Decision

| Binding gate | Result | Reason |
| --- | --- | --- |
| Official terms and public derived-display rights | Not advanced to acceptance | Anonymous official access is favorable, but technical/semantic gates fail before a public-field contract is relevant |
| Free access for 63+ daily OHLCV bars | Fail | Long daily metric history exists, but no OHLC bars are published |
| Exact 12-symbol coverage | Unproven and non-dispositive | Broad ETP coverage does not repair the missing OHLC/cadence contract |
| At-most-36-hour freshness | Fail | Quarterly files currently end at December 2025 |
| Truthful volume/price semantics | Fail for core radar | Volume excludes important consolidated-tape activity; no comparable price series is exposed |
| Bounded local/GitHub Actions operation | Fail for daily collection shape | Quarterly 20 MB-class ZIPs are research downloads, not a daily endpoint |
| Five bounded GitHub Actions probes | Not run | Schema, freshness, and metric gates fail before Step 1 and Step 2 |
| No paid plan/trial/secret exposure | Pass for download | No account or key is required |
| Public/raw retention contract | Not exercised | No file was downloaded or retained |

**Disposition: `reject as the u140 public OHLCV source; defer only as a possible
Phase 2 market-structure research input`.** No ZIP, fixture, adapter, public output,
workflow, local probe, GitHub Actions probe, or TECH-DEBT item is created.

## Current Search Boundary

After 25 Step 0 iterations, the documented non-duplicate inventory covers existing
price paths, issuer workbooks, major free/self-service APIs, commercial EOD vendors,
exchange-direct venue and consolidated products, and the official public SEC
market-structure dataset. No reviewed source simultaneously provides permanent-free
access, explicit public derived-display rights, exact 12-symbol 63+ day OHLCV,
at-most-36-hour freshness, bounded GitHub Actions operation, and truthful consolidated
volume. Resume only with new primary-source evidence or an explicit product decision
to relax one of those binding constraints.
