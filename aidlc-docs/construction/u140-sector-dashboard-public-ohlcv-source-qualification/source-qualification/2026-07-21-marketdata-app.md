# u140 Source Fact Sheet — MarketData.app Historical Candles API

**Checked**: 2026-07-21
**Candidate**: MarketData.app Historical Candles API
**Disposition**: Reject under current written terms for public Pages
**Probe status**: Not run; the candidate failed the free public-use rights gate first

## Source Facts

| Field | Value |
| --- | --- |
| Source owner | Market Data; its terms state that third-party data can remain subject to the originating licensors and exchanges |
| Data family | Historical OHLCV candles for US stocks and ETFs |
| Official docs | `https://www.marketdata.app/docs/api/stocks/candles/` |
| Endpoint | `GET https://api.marketdata.app/v1/stocks/candles/D/{symbol}/?countback=63`; one symbol per historical-candles request |
| Auth | A secret Bearer token is required for all ordinary symbols and every request. Only designated demo symbols such as AAPL work without a token. |
| Cost and no-paid evidence | Free Forever is USD 0 with 100 daily API credits, one year of history, and 24-hour-delayed stock data. This clears the preliminary history and request-count bar, but its license is Internal Use. The Commercial plan is custom-priced, requires an annual commitment, and is the listed plan for end-user display and redistribution. |
| Rate and request budget | Historical candles cost one credit per 1,000 candles. Twelve 63-candle symbol requests consume 12 minimum credits, within the Free 100-credit daily limit. |
| Format | JSON arrays with explicit success, no-data, and error status values |
| Key fields | `s`, `o`, `h`, `l`, `c`, `v`, and `t`; daily timestamps represent midnight America/New_York on the session date |
| Required symbols | The endpoint documents stocks and ETFs, making the 11 sector ETFs and SPY syntactically plausible; exact 12-symbol availability was not probed after the binding rights failure |
| Update cadence | Free accounts receive data delayed by at least 24 hours. The documentation does not state an upper bound, so it does not prove the u140 at-most-36-hour weekday freshness gate. |
| Historical range | Free Forever provides one year of historical data, sufficient in principle for 63 daily bars |
| Adjustment semantics | Daily candles default to split adjustment using the CRSP methodology. The reviewed candle contract does not document dividend adjustment or a separate adjusted-close field. |
| Attribution | No attribution option converts a self-service license into public display permission. Commercial redistribution requires exchange licensing and provider coordination. |
| Caching and raw retention | The terms require deletion of downloaded data when the subscription ends and do not grant public raw caching under a self-service plan. HTTP 203 cache responses are a provider delivery behavior, not a retention grant. No payload or fixture is stored. |
| License/public display | Pricing labels Free, Starter, and Trader as Internal Use. The redistribution policy says self-service plans are personal licenses and prohibits redistribution in any form, including embedding live or recent data in a product accessible to others. Public/end-user display is routed to a custom annual Commercial plan and exchange licenses. |
| Existing Investo overlap | No MarketData.app runtime, test, config, dependency, credential, or workflow surface exists. Existing Yahoo history/u138 remains operational evidence only and supplies neither MarketData.app data nor rights. |
| Proposed `source_name` | None; rejected before design |
| Proposed adapter path | None; rejected before design |
| Routing surfaces | None; no registry, spec, tier, market-window, segment, config, diagnostics, fixture, token, or workflow change |
| Degradation behavior | Not applicable; no runtime path is registered |

## Dated Primary-Source Evidence

Checked on 2026-07-21:

1. `https://www.marketdata.app/docs/api/stocks/candles/`
   - documents the single-symbol `/v1/stocks/candles/{resolution}/{symbol}/`
     endpoint, `countback`, daily resolutions, and stocks/ETF coverage;
   - exposes OHLCV and America/New_York timestamps with `ok`, `no_data`, and
     `error` response states;
   - defaults daily candles to CRSP-method split adjustment and charges one credit
     per 1,000 candles.
2. `https://www.marketdata.app/docs/api/authentication/`
   - requires a secret Bearer token on each ordinary request and limits anonymous
     access to designated demo symbols;
   - documents a one-IP-at-a-time account restriction.
3. `https://www.marketdata.app/pricing/`
   - lists Free at 100 daily credits, one year of historical candlesticks, and
     24-hour-delayed stock data;
   - labels Free, Starter, and Trader as Internal Use;
   - reserves end-user display and redistribution for a custom-priced Commercial
     plan requiring an annual commitment.
4. `https://www.marketdata.app/docs/account/free-accounts/`
   - confirms Free Forever history is limited to one year and data is delayed by at
     least 24 hours.
5. `https://www.marketdata.app/terms/`
   - grants personal, non-professional use and prohibits making data available to
     others without a supplemental commercial-use addendum;
   - requires deletion of downloaded subscription data when the subscription ends.
6. `https://www.marketdata.app/docs/account/data-policies/data-redistribution/`
   - classifies every self-service plan as a personal license and forbids
     redistribution in any form;
   - includes embedding live or recent data in a product accessible to others and
     says commercial redistribution requires exchange licenses.
7. `https://www.marketdata.app/terms/commercial-use-addendum/`
   - permits display redistribution only for Commercial Services and leaves venue
     licensing, reporting, and fees with the customer.

The Free technical contract is sufficient for a bounded 12-symbol test, but its
Internal Use license is not sufficient for a public Pages dashboard. The provider
routes end-user display and redistribution to a custom annual Commercial plan plus
applicable exchange licenses, which fails both the no-paid and explicit free public
derived-display gates.

## Deduplication Evidence

A repository scan across `src/`, `tests/`, `scripts/`, `.github/`, `CONTRIBUTING.md`,
dependency configuration, AIDLC plans, and requirements found no `marketdata.app`,
`api.marketdata.app`, or `MARKETDATA_TOKEN` surface. Adding it would introduce a
Bearer-token and single-IP trust boundary while leaving the public-use gate failed.

## Gate Decision

| Binding gate | Result | Reason |
| --- | --- | --- |
| Official terms and public derived-display rights | Fail | Every self-service plan is Internal Use/personal, while end-user display and redistribution require Commercial Services and exchange licenses |
| Free access for 63+ daily OHLCV bars | Preliminary pass | Free provides one year of history and 100 daily credits; twelve 63-candle requests fit the documented budget |
| Exact 12-symbol coverage and freshness | Not run | Fail-fast after the binding rights failure; exact symbols, holidays, and dividend adjustment remain unproven |
| Five bounded GitHub Actions probes | Not run | A provider account/token and rotating-runner IP behavior are unjustified after rejection |
| No paid plan/trial/secret exposure | Fail | Public display is a custom annual Commercial product and ordinary symbols require a secret token |
| Public/raw retention contract | Fail | Self-service redistribution is prohibited and downloaded data must be deleted when the subscription ends |

**Disposition: `reject under current written terms`.** Reconsider only with a
zero-cost written agreement that explicitly covers Investo's public derived fields,
attribution, caching, raw retention, GitHub Actions access, and GitHub Pages delivery,
plus any required exchange permissions. No account/token, local probe, GitHub Actions
probe, adapter, fixture, Pages output, or TECH-DEBT item is created.
