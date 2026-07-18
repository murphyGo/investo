# u140 Source Fact Sheet — Financial Modeling Prep

**Checked**: 2026-07-19
**Candidate**: Financial Modeling Prep historical end-of-day prices
**Disposition**: Reject under current written terms for public Pages
**Probe status**: Not run; the candidate failed the public-rights gate first

## Source Facts

| Field | Value |
| --- | --- |
| Source owner | Financial Modeling Prep / FMP |
| Data family | Historical stock end-of-day price and volume data |
| Official docs | `https://site.financialmodelingprep.com/developer/docs/stable/historical-price-eod-full` |
| Endpoint | `GET https://financialmodelingprep.com/stable/historical-price-eod/full?symbol=AAPL`; official docs also expose separate non-split-adjusted and dividend-adjusted paths |
| Auth | Required API key, documented as `apikey=YOUR_API_KEY` query authorization |
| Cost and no-paid evidence | Basic is free and includes end-of-day historical data; official comparison lists five years of history |
| Rate and bandwidth limit | Basic: 250 calls/day and 500 MB trailing-30-day bandwidth |
| Format | Structured API response; exact payload shape was not retained or probed after rejection |
| Key fields | Official full endpoint documents date-level open, high, low, close, volume, price changes, percentage changes, and VWAP |
| Required symbols | `XLC, XLY, XLP, XLE, XLF, XLV, XLI, XLB, XLRE, XLK, XLU, SPY`; exact coverage was not probed after the binding rights failure |
| Update cadence | End-of-day; Basic is explicitly an end-of-day plan |
| Historical range | Five years on the Basic comparison table, sufficient in principle for the 63-bar minimum |
| Adjustment semantics | FMP exposes separate `full`, `non-split-adjusted`, and `dividend-adjusted` endpoints. The non-split endpoint explicitly avoids split adjustment and the dividend endpoint explicitly adjusts for dividends; the default full endpoint's complete corporate-action convention was not inferred without a payload/contract probe. |
| Attribution | Attribution alone does not satisfy the required display/license agreement |
| Caching and raw retention | Basic has a bandwidth limit, but no public display or retention permission for Investo was established; no FMP payload or fixture is stored |
| License/public display | Pricing classifies Basic as Individual usage and states that displaying or redistributing FMP data requires a specific Data Display and Licensing Agreement. General terms prohibit integrating data into third-party-accessible applications and multi-user display without a specific agreement. |
| Existing Investo overlap | No FMP runtime, test, config, dependency, or workflow surface exists. Existing Yahoo history/u138 remains operational evidence only and does not supply FMP rights. |
| Proposed `source_name` | None; rejected before design |
| Proposed adapter path | None; rejected before design |
| Routing surfaces | None; no registry, spec, tier, market-window, segment, config, diagnostics, fixture, secret, or workflow change |
| Degradation behavior | Not applicable; no runtime path is registered |

## Dated Primary-Source Evidence

Checked on 2026-07-19:

1. `https://site.financialmodelingprep.com/developer/docs/pricing`
   - lists Basic as free, 250 calls/day, end-of-day historical data, five years of
     history, Individual usage, and 500 MB trailing-30-day bandwidth;
   - states that display or redistribution requires a specific Data Display and
     Licensing Agreement.
2. `https://site.financialmodelingprep.com/developer/docs/terms-of-service`
   - prohibits integrating FMP data into tools or applications accessible by third
     parties and prohibits multi-user data display without a specific agreement;
   - also restricts distribution of FMP data or information derived from it.
3. `https://site.financialmodelingprep.com/developer/docs/quickstart`
   - documents API-key authorization and the stable base URL;
   - identifies `/historical-price-eod/full?symbol=AAPL` as the full price-and-volume
     endpoint.
4. `https://site.financialmodelingprep.com/developer/docs/stable/historical-price-eod-full`
   - documents daily open, high, low, close, volume, price-change, percentage-change,
     and VWAP fields.
5. `https://site.financialmodelingprep.com/developer/docs/stable/historical-price-eod-non-split-adjusted`
   and `https://site.financialmodelingprep.com/developer/docs/stable/historical-price-eod-dividend-adjusted`
   - document distinct unadjusted-for-splits and dividend-adjusted EOD contracts.

The free quota and five-year range are ample for a once-daily 12-symbol probe in
principle. They do not clear the intended public GitHub Pages use. Investo does not
infer a public derived-display right from an individual plan when the provider
requires a separate display/license agreement and restricts derived-data
distribution.

## Deduplication Evidence

A repository scan across `src/`, `tests/`, `scripts/`, `.github/`, `CONTRIBUTING.md`,
dependency configuration, AIDLC plans, and requirements found no Financial Modeling
Prep or FMP adapter, registration, source spec, tier/window/segment route, fixture,
credential, dependency, or workflow. Adding it would introduce a new API-key trust
boundary and would still leave the public rights gate unresolved.

## Gate Decision

| Binding gate | Result | Reason |
| --- | --- | --- |
| Official terms and public derived-display rights | Fail | Individual usage; display/redistribution needs a specific agreement; no Investo agreement exists |
| Free access for 63+ daily OHLCV bars | Preliminary pass | Basic is free and lists five years of EOD history at 250 calls/day |
| Exact 12-symbol coverage and freshness | Not run | Fail-fast after the binding rights failure |
| Five bounded GitHub Actions probes | Not run | A new credential path and provider payload testing are unjustified after rejection |
| No paid plan/trial/secret exposure | Partial | No paid plan or trial is required, but an API key is required |
| Public/raw retention contract | Not established | No public display/license agreement; no payload retained |

**Disposition: `reject under current written terms`.** Reconsider only with a
specific agreement that explicitly covers Investo's public derived fields,
attribution, caching, raw-retention policy, and GitHub Pages delivery. No account/key,
local probe, GitHub Actions probe, adapter, fixture, Pages output, or TECH-DEBT item
is created.
