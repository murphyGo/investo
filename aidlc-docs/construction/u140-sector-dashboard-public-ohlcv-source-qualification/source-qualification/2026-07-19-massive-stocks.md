# u140 Source Fact Sheet — Massive Stocks API

**Checked**: 2026-07-19
**Candidate**: Massive Stocks aggregates API, formerly Polygon.io
**Disposition**: Reject under current written terms for public Pages
**Probe status**: Not run; the candidate failed the public-rights gate first

## Source Facts

| Field | Value |
| --- | --- |
| Source owner | Massive.com, Inc. |
| Data family | Historical and current US stock/ETF aggregate bars and reference data |
| Official docs | `https://massive.com/docs/rest/stocks/aggregates/custom-bars` |
| Endpoint | `GET https://api.massive.com/v2/aggs/ticker/{stocksTicker}/range/{multiplier}/{timespan}/{from}/{to}`; use `1/day` for daily bars |
| Auth | Required `apiKey` query credential |
| Cost and no-paid evidence | Stocks Basic is USD 0/month and includes all US stock tickers, end-of-day data, two years of history, corporate actions, technical indicators, and minute aggregates |
| Rate limit | Five API calls/minute on Stocks Basic; 12 symbols require at least 12 ticker-specific calls plus pagination, technically feasible within a bounded daily schedule |
| Format | JSON with request ID, status, counts, optional `next_url`, and result objects |
| Key fields | Timestamp, open, high, low, close, volume, optional VWAP and transaction count, ticker, results count, and adjustment flag |
| Required symbols | `XLC, XLY, XLP, XLE, XLF, XLV, XLI, XLB, XLRE, XLK, XLU, SPY`; all-US-ticker coverage makes the universe plausible, but exact rows were not probed after rejection |
| Update cadence | End-of-day on free Basic; exact weekday availability time was not established before the rights failure |
| Historical range | Two years on Stocks Basic, sufficient in principle for the 63-bar minimum |
| Adjustment semantics | `adjusted=true` by default adjusts for splits; `false` returns unadjusted bars. The endpoint does not claim dividend-adjusted aggregate prices. |
| Empty interval semantics | No bar is produced when no eligible trades occur in an interval |
| Attribution | Attribution cannot replace the express written consent required for third-party display or derived works |
| Caching and raw retention | Terms require deletion after account termination and provide no Investo public retention grant; no Massive payload or fixture is stored |
| License/public display | Individual access is personal, non-business, and non-commercial. Market Data Terms prohibit apps for other end users and third-party display/distribution of Market Data or derived charts, analytics, research, and other works without express written consent. |
| Existing Investo overlap | No Massive/Polygon.io runtime, test, config, dependency, or workflow surface exists. Existing Yahoo history/u138 remains operational evidence only and does not supply Massive rights. |
| Proposed `source_name` | None; rejected before design |
| Proposed adapter path | None; rejected before design |
| Routing surfaces | None; no registry, spec, tier, market-window, segment, config, diagnostics, fixture, key, or workflow change |
| Degradation behavior | Not applicable; no runtime path is registered |

## Dated Primary-Source Evidence

Checked on 2026-07-19:

1. `https://massive.com/pricing?product=stocks`
   - lists Stocks Basic at USD 0/month with all US stock tickers, five calls/minute,
     two years of history, end-of-day data, reference data, corporate actions,
     technical indicators, and minute aggregates;
   - labels the plan Individual use.
2. `https://massive.com/docs/rest/stocks/aggregates/custom-bars`
   - documents the ticker-specific aggregate endpoint, `apiKey` authentication,
     daily timespan, raw/split-adjusted selection, pagination, and OHLCV/VWAP fields;
   - states that no bar is emitted for an interval without eligible trades.
3. `https://massive.com/legal/individuals-terms-of-service`
   - grants access solely for personal, non-commercial, and non-business purposes;
   - incorporates the Market Data Terms.
4. `https://massive.com/legal/market-data-terms-of-service`
   - grants Market Data use only for personal, non-business, non-commercial purposes
     and prohibits building an application for end users other than the subscriber;
   - prohibits third-party display, dissemination, publication, or distribution of
     Market Data and data, charts, analytics, research, or other derived works without
     prior express written consent;
   - requires deletion of Market Data after account termination.

Massive is one of the clearest technical fits reviewed so far, but it is also an
explicit legal mismatch. Investo's public Pages dashboard is an application for other
end users and publishes derived analytics. Both uses are named by the binding terms,
so attribution or retaining only scores cannot create permission.

## Deduplication Evidence

A repository scan across `src/`, `tests/`, `scripts/`, `.github/`, `CONTRIBUTING.md`,
dependency configuration, AIDLC plans, and requirements found no Massive or
Polygon.io adapter, registration, source spec, tier/window/segment route, fixture,
credential, dependency, or workflow. Adding it would introduce a new query-key trust
boundary and would still violate the public-use contract.

## Gate Decision

| Binding gate | Result | Reason |
| --- | --- | --- |
| Official terms and public derived-display rights | Fail | Other-end-user apps and third-party derived analytics/research display are prohibited without consent |
| Free access for 63+ daily OHLCV bars | Preliminary pass | Basic is free, covers all US tickers, and provides two years of EOD aggregates |
| Exact 12-symbol coverage and freshness | Not run | Fail-fast after the binding rights failure |
| Five bounded GitHub Actions probes | Not run | A new key and provider-payload testing are unjustified after rejection |
| No paid plan/trial/secret exposure | Partial | No paid plan is required for personal EOD access, but an API key is required and public rights are absent |
| Public/raw retention contract | Fail | Public derived works are restricted; termination also requires deletion |

**Disposition: `reject under current written terms`.** Reconsider only with Massive's
express written consent covering Investo's public derived fields, attribution,
caching, raw-retention policy, and GitHub Pages delivery. No account/key, local
probe, GitHub Actions probe, adapter, fixture, Pages output, or TECH-DEBT item is
created.
