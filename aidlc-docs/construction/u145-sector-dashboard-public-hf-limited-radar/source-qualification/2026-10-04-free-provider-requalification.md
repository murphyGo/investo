# u145 — Free provider replacement qualification

> Superseded decision: after this qualification report, the user explicitly selected public Yahoo implementation despite unverified permission. The [Yahoo amendment](2026-10-04-yahoo-public-amendment.md) records the operator exception and active contract; the findings below remain historical qualification evidence.

**Checked**: 2026-10-04, through 23:18 KST (14:18 UTC)
**Decision**: Replacement authorized; free providers only; no replacement qualified
**Implementation baseline**: `abdd2897` on `codex/u145-resume-20260922`

## User decision and result

The user requested `다른 공급원으로 교체 진행시켜`, then clarified
`지금은 무료 공급원만 고려해줘`. This authorizes replacement work while retaining
the zero-cost requirement. Paid plans, trials that require future payment, and paid
display licenses are excluded. No account, subscription, credential or external
message was created during this investigation.

No examined candidate currently establishes all of free ongoing access, suitable
daily ETF history, public derived-display rights and usable automated delivery.
This is a bounded investigation result, not a claim that no such provider exists.
The replacement is **not implemented or complete**. Existing production code remains
HF-specific and no alternative source is silently substituted.

## Actual HF blocker

A bounded unauthenticated request to the documented SPY download-token endpoint
returned HTTP 503 and closed provider code `data_paused`. The response explicitly
attributes the pause to dataset restructuring and says the returning segment will
start in March 2022 with IEX data. It does not provide a recovery date.

This corrects the previous transient-server-error-only diagnosis. The response
does not establish whether the existing credential remains valid. Metadata or
homepage availability does not establish download availability. Do not dispatch
more identical five-run batches while this explicit pause continues.

Endpoint: <https://api.hfdatalibrary.com/v1/download-token/SPY?timeframe=daily&format=parquet&version=clean>

## Candidate evidence

| Candidate | Current primary evidence and access | Public-use / operational finding | Disposition |
| --- | --- | --- | --- |
| Twelve Data Free | Business pricing identifies Free as internal non-display usage; external display appears in paid Business access | The free tier does not establish this public Pages use; paid options are outside the user's scope | Reject for this free public replacement |
| Alpha Vantage | Terms section 2 grants personal, non-commercial use; activities beyond private individual analysis require a written agreement | No no-cost agreement for public derived display is available in this workspace | Reject under the currently published grant |
| Alpaca | Official support explicitly states that API data cannot be redistributed | No separate written grant covering the proposed public derived output is available | Reject pending an applicable no-cost grant |
| Stooq | Direct bounded SPY daily CSV request returned HTTP 200, `text/html`, 796 bytes; no CSV header, with a JavaScript browser-verification challenge | Automated historical bars were not obtained; public derived-display terms were not established; no challenge bypass attempted | Defer; current transport gate fails |
| StashGamma | Official docs advertise a free authenticated EOD JSON route, 300 requests/hour, 800/day and 4,000/week | Terms section 4 restricts distribution and derivative works without permission; section 6 reserves commercial use. API documentation does not supply the missing public grant | Defer pending an explicit no-cost public-use grant and operator-owned key |
| HF Market Data (`hfmarketdata.io`) | Search-indexed official homepage advertises free stock/ETF daily bars and anonymous access. It is a different service from HF Data Library | Direct homepage and documented-shape SPY ETF requests failed TLS negotiation, including outside the sandbox. Web fetch also returned 502. Complete data-license/provenance evidence was not retrieved; no bars or freshness were verified | Defer; promising advertised shape, unqualified delivery and rights |
| Convex Open Data | Official page offers free JSON/CSV and attribution-based reuse of its own indices | Listed datasets are macro series and proprietary indices; no SPY-plus-sector daily OHLCV contract was established. Macro indicators are not substitutes for ETF prices | Reject as a direct replacement; no new macro-source work |
| Yahoo chart path | Existing briefing integration is documented in the u140 investigation; current terms/about retrieval failed with 999/429 through the web tool | This turn did not establish a new public derived-display grant. Existing briefing use is not evidence accepting a new dashboard source | Defer; no change to existing briefing integration |

### Primary-source links

- Twelve Data: [Business pricing](https://twelvedata.com/pricing-business),
  [commercial and personal usage](https://support.twelvedata.com/en/articles/5332349-commercial-and-personal-usage).
- Alpha Vantage: [terms](https://www.alphavantage.co/terms_of_service/).
- Alpaca: [redistribution policy](https://alpaca.markets/support/redistribute-alpaca-api).
- Stooq: [bounded SPY daily request](https://stooq.com/q/d/l/?s=spy.us&i=d&d1=20260601&d2=20261002).
- StashGamma: [API contract](https://stashgamma.com/developer-docs),
  [terms](https://stashgamma.com/terms).
- HF Market Data: [official homepage](https://www.hfmarketdata.io/),
  [terms introduction](https://www.hfmarketdata.io/terms). Search-indexed claims
  are not recorded as a successful live endpoint or complete license check.
- Convex: [open-data contract](https://convextrade.com/open-data).
- Yahoo: [terms URL attempted](https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html),
  [API terms URL attempted](https://legal.yahoo.com/us/en/yahoo/terms/product-atos/apiforydn/index.html).

Direct IEX HIST was also reconsidered against the existing
`u140-sector-dashboard-public-ohlcv-source-qualification/source-qualification/2026-07-22-iex-hist-direct.md`
fact sheet and the current [official HIST delivery description](https://iextrading.com/trading/market-data/).
It remains whole-feed PCAP rather than bounded ticker-filtered daily bars. Historical
9–21 GB/day measurements are **July evidence, not a new October size measurement**.
No PCAP download or decoder implementation was attempted.

## Acceptance boundary for the replacement

Retain the limited u145 product rather than silently importing stricter u140 scope:

1. Free ongoing access and an identifiable primary source or licensed provider;
   explicit support for the intended public derived output and attribution.
2. SPY and the ten currently supported sector ETFs, with 64 valid benchmark
   observations for the 63D metrics, matching sector dates and adjustment semantics.
   XLRE coverage can be reconsidered only with evidence and a documented model change.
3. Freshness for the latest completed US trading session; unknown or stale data
   cannot qualify a new snapshot.
4. Bounded unattended requests, response sizes, retries and processing. No browser
   challenge bypass, hidden endpoint, or removal of resource checks.
5. Source-specific price and adjustment labels. No volume-based metrics or claims
   of consolidated market data without evidence. The current IEX labels cannot be
   carried over to an unrelated feed.
6. Five successful isolated production-adapter probes on the reviewed replacement
   commit before separate Pages activation. The existing visual waiver persists.

## Concrete implementation surfaces once a source qualifies

| Surface | Required change |
| --- | --- |
| Functional Design and NFR requirements | Amend provider, endpoint, rate, auth, rights, adjustment and failure contracts; retain free-only cost and public-output constraints |
| `src/investo/models/sector_public.py` | Replace pinned HF source/license identity and IEX-only metric semantics truthfully; decide schema migration and XLRE coverage from evidence |
| `src/investo/sector_dashboard/hf_data.py` and replacement adapter | Implement the selected documented transport and parser with bounded, redacted failures; never add an unqualified fallback |
| `public_metrics.py`, `public_probe.py`, `public_render.py` | Reuse mathematical kernels; update semantic wrappers, probe source identity and displayed provenance together |
| `scripts/build_sector_dashboard_public.py`, benchmark and probe workflow | Wire the selected collector, only its required credential, its synthetic worst-case benchmark and isolated live evidence |
| `scripts/check_no_paid_apis.py` and `tests/unit/sources/test_no_paid_apis.py` | Replace the old HF-specific network allow-list with equally narrow selected-provider checks; preserve the general no-paid guard |
| Sector/model tests | Add provider response and failure contracts, calendar/freshness tests, correct source/adjustment labels and private-u139 compatibility |
| Registry / tier / segment maps | No new daily-briefing plugin, registry entry or route: the dashboard keeps its isolated collector boundary |

No speculative source abstraction is added before selection. There is no retained
real last-good public sector snapshot to republish as a workaround; previous live
probes used an in-memory output contract.

## Work state

- [x] Record replacement authorization and the user's free-only constraint.
- [x] Correct the HF failure diagnosis using the actual bounded API response.
- [x] Recheck existing candidates and investigate new free API candidates.
- [x] Identify concrete implementation and test surfaces without changing runtime behavior.
- [ ] Qualify a free provider's rights, actual symbols/history and freshness.
- [ ] Amend the provider contract and implement/test the replacement.
- [ ] Complete five qualifying isolated runs; retain separate activation review.

The next useful evidence is a working documented HF Market Data route plus its
complete data license/provenance, or an explicit no-cost public-derived-use grant
from a technically suitable free API. No provider was contacted, no key was
requested and no future/background monitoring was scheduled.

This investigation changes planning/runbook documents only. Source, tests, guard
implementation, workflow, public output and deployment are unchanged. Documentation
checks are recorded in the session audit; previous application test results remain
historical evidence and are not reported as newly rerun tests.
