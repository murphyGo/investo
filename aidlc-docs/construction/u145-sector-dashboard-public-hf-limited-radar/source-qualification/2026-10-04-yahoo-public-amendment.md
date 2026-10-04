# u145 Yahoo public-source amendment

**Date**: 2026-10-04
**Authority**: User: `그럼 그냥 공개용으로 진행해줘`, following the explanation of
unverified Yahoo automated-collection and public-use permissions. Free-only remains binding.
**Scope**: Replace the active HF collector with Yahoo chart daily prices for the public
sector radar. This supersedes the prior source-selection hold for this unit only.

## Decision and requirements

The user authorizes implementation for public use despite unresolved permission evidence.
This is an operator decision, not provider consent, a license grant, or a legal finding.
No CC BY or IEX license is attributed to Yahoo. The public provenance records permission
as unverified. The u140 strict source qualification and the private u139 NAV product remain
unchanged. No paid plan, key, proxy, challenge bypass, or external provider contact is added.

The 2026-10-04 local Yahoo collection returned all 12 identities, 126 daily rows each,
ending 2026-10-02. That is reachability/shape evidence, not five Actions successes or
public-display permission. All application contracts and tests below must still pass.

## Functional Design amendment

This document supersedes HF-specific R1-R10/R15, E1/E9a and associated provenance rules
for the active implementation; historical HF acceptance evidence remains historical.

- Sole endpoint: HTTPS `query2.finance.yahoo.com/v8/finance/chart/{ticker}`. No fallback,
  configurable host, credentials, redirects or browser automation.
- Fixed universe: SPY plus all eleven Select Sector ETFs, now including XLRE.
- Query: daily regular-session bars; explicit period bounds from target minus 200 calendar
  days through midnight New York after the latest completed target session. No current
  intraday bar is used. Target resolution retains the versioned NYSE calendar.
- Validate the complete returned JSON within a fixed size/row limit: one result, no chart
  error, matching symbol, USD, ETF, New York timezone, daily granularity, equal-length OHLCV
  arrays, strictly increasing unique trading dates, finite positive prices, valid OHLC
  bounds and nonnegative integer volume. Reject malformed/null rows rather than skipping.
- Use provider `quote.close` prices, not `adjclose` or a reconstructed total-return series.
  Label them Yahoo daily closes; adjustment metadata says provider close, with no stronger
  dividend or consolidated-feed claim. Metrics remain simple price returns, never NAV.
- Keep the final 64 SPY dates and matching sector dates plus endpoint evidence only after
  validating all returned rows. Preserve same-as-of comparability and stale-data rejection.
- Public schema version 2 and source `yahoo-chart-daily-v2`; price metric fields use
  `price_*`, market scope is `provider_reported_us_equity`. Old HF snapshots cannot be
  reinterpreted as Yahoo. There is no real previously published HF sector snapshot to migrate.
- Normal coverage requires all eleven sectors; partial coverage permits eight through ten.
  XLRE follows the same availability rules as every other sector. No proxy filling.
- Source attribution is Yahoo Finance with a source link. No HF/IEX/CC BY claim. Public
  artifacts remain derived-only, with correct as-of, coverage, method and disclaimer.
- Mathematical kernels, rank/regime policy and private u139 outputs remain unchanged.

## NFR amendment

Retain 120-second collection, 30-second CPU and 256-MiB incremental RSS ceilings. Tighten
the new JSON shape to 256 rows/symbol and 1 MiB/response. Concurrency is at most two,
36 requests/minute and 36 attempts/collection (12 symbols x at most three attempts).
These are conservative application ceilings, not a claimed provider quota. Retry only
429, server and transport errors, honoring bounded Retry-After; 401/403 fail without retry.
Use a fixed User-Agent, stripped ambient auth/cookies/query parameters, no observing hooks,
bounded response streaming and closed error codes. Accept only absent/identity response
Content-Encoding before reading any body, preventing decompression before the byte gate. No secret is necessary or forwarded.

The isolated probe still writes only aggregate evidence; qualification now requires all
12 symbols / 11 comparable sectors. The synthetic benchmark exercises the maximum accepted
response size and every valid trading date in the bounded 200-day window; excessive-row
rejection is tested separately. New raw provider rows are not committed, published or logged. Visual acceptance
remains `WAIVED / NOT_EXECUTED`; no new Browser gate is introduced.

FR-022/NFR-008 have a u145-specific operator exception for unverified Yahoo permission.
Freshness, data validity, no-paid constraints, output checks and five successful isolated
probes remain required. Step 6 public activation is still a separate concrete rollout;
this implementation prepares it without merging main or enabling a schedule.

## Implementation sequence

1. Amend source/model identity and source-aware metric/render contracts in place.
2. Replace `hf_data.py` with `yahoo_data.py`, retaining bounded transport behavior and
   covering JSON/date/row identity, retries, cancellation and resource limits with tests.
3. Switch probe CLI, benchmark, workflow and narrow provider guard; no HF credential.
4. Verify model/metrics/render/store/private compatibility, full quality gates and an
   independent review. Exercise live collection without retaining raw payloads.
5. Record exact evidence and remaining Actions/activation work. Prior user authorization
   for scoped branch commit/push and isolated probes persists; no approval is inferred
   for main integration, public activation or unrelated dirty work.

Functional Design and NFR are amended here before implementation, under the explicit
source-replacement/public-use decision; routine implementation choices do not require
another approval round. Source URLs and date bounds are fixed in code and in guard tests.
