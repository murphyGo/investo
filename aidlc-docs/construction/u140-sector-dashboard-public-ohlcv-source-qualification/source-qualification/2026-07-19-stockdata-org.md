# u140 Source Fact Sheet — StockData.org EOD API

**Checked**: 2026-07-19
**Candidate**: StockData.org End-of-Day Historical Data API
**Disposition**: Reject under current written terms for public Pages
**Probe status**: Not run; the candidate failed the free-history and public-use
rights gates first

## Source Facts

| Field | Value |
| --- | --- |
| Source owner | StockData.org; its documentation says US stock trading data is sourced from IEX |
| Data family | End-of-day historical data for US stocks, with daily through yearly intervals |
| Official docs | `https://www.stockdata.org/documentation` |
| Endpoint | `GET https://api.stockdata.org/v1/data/eod?symbols={symbol}&interval=day&date_from={date}&date_to={date}&api_token={token}`; the EOD endpoint accepts one symbol per request |
| Auth | Required API token passed in the `api_token` query parameter |
| Cost and no-paid evidence | Free is USD 0 with 100 requests/day but only one month of EOD history. Basic is USD 29/month, or USD 24/month when billed annually, and is the first listed tier with one year of EOD history. |
| Rate and request budget | Twelve symbol-specific requests fit the Free daily request count, but the one-month Free history cap cannot provide the required 63 trading days. |
| Format | JSON by default; CSV is optional |
| Key fields | `date`, `ticker`, `open`, `high`, `low`, `close`, and `volume` |
| Required symbols | The documentation covers US stock data, making the 11 sector ETFs and SPY syntactically plausible; exact 12-symbol availability was not probed after the binding failures |
| Update cadence | The endpoint is described as end-of-day data, but the reviewed public contract does not pin a weekday completion time sufficient to prove the u140 36-hour freshness gate |
| Historical range | Free is limited to one month of EOD data, below 63 trading days; Basic provides one year and is paid |
| Adjustment semantics | The EOD documentation says data is adjusted for splits. It does not state that EOD prices are dividend-adjusted or expose a separate adjusted-close field. |
| Attribution | The reviewed documentation, pricing, and general terms do not publish an attribution option that grants public derived-display rights |
| Caching and raw retention | No explicit public caching, raw-retention, or derived-field publication grant was found in the reviewed public contract. No payload or fixture is stored. |
| License/public display | The current terms grant access, use, and downloads solely for personal, non-commercial use, reserve ungranted rights, and prohibit commercial endeavors unless specifically endorsed or approved. They do not grant Investo public derived-display rights. |
| Existing Investo overlap | No StockData.org runtime, test, config, dependency, credential, or workflow surface exists. Existing Yahoo history/u138 remains operational evidence only and supplies neither StockData.org history nor rights. |
| Proposed `source_name` | None; rejected before design |
| Proposed adapter path | None; rejected before design |
| Routing surfaces | None; no registry, spec, tier, market-window, segment, config, diagnostics, fixture, token, or workflow change |
| Degradation behavior | Not applicable; no runtime path is registered |

## Dated Primary-Source Evidence

Checked on 2026-07-19:

1. `https://www.stockdata.org/documentation`
   - documents the token-authenticated `/v1/data/eod` endpoint, one symbol per
     request, date filters, JSON/CSV output, and daily through yearly intervals;
   - exposes date, ticker, OHLC, and volume fields and returns an empty data object
     when no rows exist;
   - says EOD data is split-adjusted and says US stock trading data is sourced from
     IEX.
2. `https://www.stockdata.org/pricing`
   - lists Free at 100 requests/day with only one month of EOD data;
   - lists Basic at USD 29/month, or USD 24/month billed annually, with one year of
     EOD data.
3. `https://www.stockdata.org/tos`
   - limits the general license to personal, non-commercial use and reserves rights
     not expressly granted;
   - says commercial endeavors require specific endorsement or approval.

The Free request count can cover 12 symbol-specific calls, but its contractual
history window is shorter than the required 63 trading days. The first plan with
enough listed history is paid. Independently, the current terms do not authorize a
public Pages product or its derived displays.

## Deduplication Evidence

A repository scan across `src/`, `tests/`, `scripts/`, `.github/`, `CONTRIBUTING.md`,
dependency configuration, AIDLC plans, and requirements found no StockData.org
adapter, registration, source spec, tier/window/segment route, fixture, credential,
dependency, or workflow. Adding it would introduce a query-token trust boundary
while leaving both the free-history and public-use gates failed.

## Gate Decision

| Binding gate | Result | Reason |
| --- | --- | --- |
| Official terms and public derived-display rights | Fail | Current terms grant personal, non-commercial use only and provide no Investo public derived-display approval |
| Free access for 63+ daily OHLCV bars | Fail | Free is capped at one month of EOD history; one year begins on paid Basic |
| Exact 12-symbol coverage and freshness | Not run | Fail-fast after the binding history and rights failures; daily completion time and dividend adjustment also remain unproven |
| Five bounded GitHub Actions probes | Not run | An account/token and provider-payload testing are unjustified after rejection |
| No paid plan/trial/secret exposure | Fail | Sufficient listed history requires paid Basic and every request requires a secret query token |
| Public/raw retention contract | Fail | The reviewed public terms do not grant public derived-display, caching, or raw-retention rights |

**Disposition: `reject under current written terms`.** Reconsider only if a no-cost
tier provides at least 63 daily OHLCV bars and StockData.org supplies written terms
covering Investo's public derived fields, attribution, caching, raw retention, and
GitHub Pages delivery. No account/token, local probe, GitHub Actions probe, adapter,
fixture, Pages output, or TECH-DEBT item is created.
