# u140 Source Fact Sheet — HF Data Library Daily OHLCV

**Checked**: 2026-07-22
**Candidate**: HF Data Library daily OHLCV aggregation over its U.S. equity/ETF minute-bar library
**Disposition**: Defer pending exact-universe and volume-fitness repair
**Probe status**: Provider API/data payload not requested; public documentation, license, upstream terms, repository catalog, and freshness metadata were inspected at Step 0

## Source Facts

| Field | Value |
| --- | --- |
| Source owner | Dataset/service maintained by Ahmed Elkassabgi at the University of Central Arkansas; post-March-2022 underlying market data belongs to Investors' Exchange LLC (IEX) |
| Data family | One-minute U.S. stock/ETF OHLCV with a documented daily OHLCV aggregation route |
| Official docs | `https://hfdatalibrary.com/`, `https://hfdatalibrary.com/pages/api`, `https://hfdatalibrary.com/pages/license`, `https://hfdatalibrary.com/pages/terms`, and `https://hfdatalibrary.com/pages/issues` |
| Endpoint | `GET https://api.hfdatalibrary.com/v1/bars/{ticker}/daily` with date, version, format, limit, and offset parameters inherited from the minute-bar route |
| Auth | Free API key in the `X-API-Key` header; keys expire every 30 days. The homepage also advertises no-account basic browser downloads, but no stable unauthenticated daily-file contract was fixed at Step 0. |
| Cost and no-paid evidence | Entire library and API are published as free, with no subscription or paywall. No paid tier is required for the documented history. |
| Rate and request budget | 100 downloads/minute per key. Twelve single-ticker requests would fit easily if every required symbol existed, but no key or request was made. |
| Format | JSON, CSV, or Parquet; bulk bundles and individual-ticker files are also advertised |
| Key fields | Minute and daily bars provide datetime/date, open, high, low, close, and volume; metadata exposes source and coverage dates |
| Required symbols | Public `data/tickers.json` and `data/ticker_meta.json` both include SPY, XLB, XLC, XLE, XLF, XLI, XLK, XLP, XLU, XLV, and XLY, but `XLRE` is absent. Exact fixed-universe coverage is 11/12 and fails. |
| Update cadence | Automated daily pipeline. Public `data/metadata.json` was updated 2026-07-21T12:28:39Z, reported data through 2026-07-20, no missing days, and status `operational`. This is catalog evidence, not a data-payload probe. |
| Historical range | Public metadata reports 23 years and 5,847 trading days, far beyond the required 63 bars for cataloged symbols |
| Adjustment semantics | The homepage states prices are split/dividend adjusted in both Raw and Clean versions. The reviewed daily endpoint does not expose separate adjusted-close, split-factor, or dividend fields. |
| Venue/volume semantics | Pre-March-2022 data is described as consolidated PiTrading tape. Post-March-2022 bars are IEX-only, approximately 2–3% of consolidated volume. The provider warns of zero-trade days, lower volume, OHLC differences from the full tape, and a structural break. Current volume cannot be labeled total ETF trading volume. |
| Attribution | Attribute the HF Data Library under CC BY 4.0. Any distribution of post-March-2022 data must additionally carry IEX's required text and link to the IEX Historical Data Terms of Use. |
| Caching and raw retention | CC BY 4.0 permits sharing/adaptation of the compilation and pre-2022 portion. IEX expressly permits distribution of its historical data with attribution and publishes no retention deadline in the reviewed terms. No provider payload was retained. |
| License/public display | HF Data Library grants use, sharing, adaptation, and distribution for any purpose, including commercial use, with attribution. IEX's upstream terms permit distribution/access with the fixed citation. This provisionally clears free public derived-display rights for recent IEX-sourced bars when attribution and venue limitations remain visible. |
| Existing Investo overlap | No HF Data Library/IEX HIST endpoint, key path, adapter, `SourceSpec`, route, dependency, fixture, or workflow exists |
| Proposed `source_name` | None while deferred |
| Proposed adapter path | None while deferred |
| Routing surfaces | None; no registry, spec, tier, market-window, segment, config, diagnostics, fixture, secret, dependency, or workflow change |
| Degradation behavior | Not applicable until exact coverage and metric semantics pass; a future design would need missing-symbol, expired-key, no-trade-day, and venue-limited-volume diagnostics |

## Dated Primary-Source Evidence

Checked on 2026-07-22:

1. `https://hfdatalibrary.com/`
   - publishes 1,391 U.S. stock/ETF tickers, 23+ years of one-minute OHLCV,
     daily updates, no subscription/paywall, and CC BY 4.0;
   - advertises a free API key, 100 downloads/minute, JSON/CSV/Parquet, and both
     raw and clean versions with split/dividend-adjusted prices.
2. `https://hfdatalibrary.com/pages/api`
   - fixes base URL `https://api.hfdatalibrary.com/v1`, `X-API-Key` auth, and
     30-day key expiry;
   - documents `GET /bars/{ticker}/daily` as daily OHLCV aggregated from intraday
     data and the same date/version/format/pagination parameters as the bar route.
3. `https://hfdatalibrary.com/pages/license` and
   `https://hfdatalibrary.com/pages/terms`
   - permit use, sharing, adaptation, and distribution for any purpose, including
     commercial use, with HF Data Library attribution;
   - scope the CC BY grant to the compilation/documentation/pre-2022 segment and
     preserve IEX rights and attribution requirements for post-March-2022 bars.
4. `https://www.iex.io/legal/hist-data-terms`
   - applies whether IEX historical data is obtained directly or through a third
     party;
   - expressly permits distribution/provision of access when the required IEX
     citation and link are included;
   - discloses IEX-only activity and reserves IEX's proprietary rights.
5. `https://hfdatalibrary.com/pages/issues`
   - documents the March-2022 source break from consolidated tape to IEX-only data;
   - states current volume is roughly 2–3% of consolidated volume, some tickers can
     have no IEX trades, and OHLC may differ from full-tape values;
   - says the current segment is unsuitable for studies requiring complete volume.
6. `https://github.com/elkassabgi/hfdatalibrary`
   - exposes the service/API/pipeline implementation and public catalog metadata;
   - `data/tickers.json` and `data/ticker_meta.json` independently contain the same
     11 required symbols but no `XLRE`;
   - `data/metadata.json`, read at Step 0 without retention, reported an operational
     update through 2026-07-20 with no missing days.
7. `https://uca.edu/ir/faculty-success/instructional-personnel-directory/`
   - independently lists Ahmed Elkassabgi in UCA's Economics, Finance, Insurance,
     and Risk Management department.

The candidate is materially better than the preceding paid/rights-restricted APIs:
it provisionally clears the cost and public-use gates. It still cannot satisfy u140
as currently published because a fixed required ticker is absent. Its recent volume
is a venue sample rather than total market activity, so using it without an explicit
IEX-only label would misstate the product metric. A 30-day API-key expiry also needs
an unattended GitHub Actions rotation contract before acceptance.

## Deduplication Evidence

A repository scan across AIDLC docs, requirements, `src/`, `tests/`, `scripts/`,
`.github/`, dependencies, and contribution guidance found no `hfdatalibrary`,
`api.hfdatalibrary.com`, IEX HIST/PiTrading adapter, API-key path, daily-bar endpoint,
registry entry, `SourceSpec`, route, fixture, dependency, secret, or workflow. Public
provider metadata was inspected read-only and was not copied into the repository.

## Gate Decision

| Binding gate | Result | Reason |
| --- | --- | --- |
| Official terms and public derived-display rights | Provisional pass | CC BY permits share/adapt/distribute; IEX historical terms permit redistribution with mandatory attribution |
| Free access for 63+ daily OHLCV bars | Preliminary pass for cataloged symbols | Free API/daily aggregation and 23+ years are documented, with no paid dependency |
| Exact 12-symbol coverage | Fail | Public catalog contains 11/12 required tickers; `XLRE` is absent |
| At-most-36-hour freshness | Preliminary metadata pass | Repository metadata was current through the last completed trading day at the checked timestamp; payload behavior remains unprobed |
| Truthful volume/price semantics | Fail for unqualified total-volume claims | Current rows represent IEX-only activity, not consolidated U.S. trading; full-tape OHLC can differ |
| Five bounded GitHub Actions probes | Not run | Exact-universe failure blocks Step 1/Step 2; recurring 30-day key expiry also lacks an operations contract |
| No paid plan/trial/secret exposure | Pass on cost; auth unprobed | Key is free but expires every 30 days; no account/key was created or stored |
| Public/raw retention contract | Provisional pass with attribution | CC BY plus IEX distribution terms permit reuse; no payload was retained during Step 0 |

**Disposition: `defer pending exact-universe and volume-fitness repair`.** Reconsider
only after the public catalog contains `XLRE`, the dashboard contract explicitly names
current price/volume as IEX-only or supplies consolidated-volume evidence, and a free
unattended auth/rotation path is fixed. Then repeat Step 0 and proceed to a bounded
12-symbol local probe. No account, key, API/data payload, fixture, runtime adapter,
public output, GitHub Actions probe, or TECH-DEBT item is created.
