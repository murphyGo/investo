# u145 public sector dashboard cross-check

## Scope and authority

Scope: FR-022, NFR-002/003/004/005/006/007/008; u145 Functional Design R1–R33 and
NFR acceptance criteria AC-1.1–AC-6.6. Apply the
[Yahoo amendment](../../aidlc-docs/construction/u145-sector-dashboard-public-hf-limited-radar/source-qualification/2026-10-04-yahoo-public-amendment.md)
to historical HF/IEX wording. Private u139 and strict u140 contracts are unchanged.

The user authorized free Yahoo public implementation despite unresolved permission on
2026-10-04, and authorized main integration/publication/scheduling with `진행시켜` following
the Step 5 closeout. Permission remains `unverified`: this is an explicit operator exception,
not provider consent. Actual Browser visual acceptance remains **WAIVED / NOT_EXECUTED**.

**Status: original activation and the data-first presentation follow-up are complete.**
Original full regression and live deployment are recorded in the
[public closeout](../sessions/2026-10-10-u145-public-closeout.md).
The user's 2026-10-10 presentation instruction supersedes historical source-first
ordering as recorded in the [UI session](../sessions/2026-10-10-u145-data-first-ui.md).
No Browser or license-verification PASS is inferred.

## Evidence key

Paths are repository-relative. Each entry pairs implementation with executable evidence.

| Key | Implementation and tests |
| --- | --- |
| A | `src/investo/sector_dashboard/yahoo_data.py`; `tests/unit/sector_dashboard/test_yahoo_data.py` |
| M | `src/investo/models/sector_public.py`, `public_metrics.py`, `metric_kernels.py`; `tests/unit/models/test_sector_public.py`, `test_public_metrics.py`, `test_metric_kernels.py` |
| R | `src/investo/sector_dashboard/public_render.py`; `tests/unit/sector_dashboard/test_public_render_store.py` |
| S | `src/investo/sector_dashboard/public_store.py`; transactional, symlink, corruption, interruption and last-good tests in `test_public_render_store.py` |
| B | `src/investo/sector_dashboard/public_build.py`, `scripts/publish_sector_dashboard.py`; `test_public_build.py` |
| P | `public_probe.py`, `scripts/build_sector_dashboard_public.py`, `sector-dashboard-probe.yml`; `test_public_probe.py` and five exact-commit Actions runs |
| W | `.github/workflows/sector-dashboard.yml`, `.github/workflows/pages.yml`, `mkdocs.yml`; static workflow and actual isolated git-shell tests in `test_public_build.py` |
| G | `_internal/sector_public_summary.py`, `scripts/check_no_paid_apis.py`; summary/sentinel tests and `tests/unit/sources/test_no_paid_apis.py` |
| U | `tests/unit/sector_dashboard/test_private_{cli,input,render}.py`, `test_metrics.py`, `test_regime.py`; unchanged private models/CLI and NAV golden contracts |
| O | `docs/sector-dashboard-public-runbook.md`, `docs/sector-dashboard-probe-runbook.md`, current session and Actions evidence |

## Functional rules

PASS below means the amended implementation and executable contract match; rollout acceptance
is completed only when the operational evidence in the session is closed.

| Rule | Active interpretation | Evidence | Status |
| --- | --- | --- | --- |
| R1 | Sole fixed Yahoo endpoint; no provider fallback | A, G | PASS |
| R2 | SPY plus all eleven sectors, fixed allowlist | A, M | PASS |
| R3 | SPY defines calendar/as-of; no benchmark means no new page | A, M, B first/auth failure | PASS |
| R4 | XLRE follows normal availability rules; always one public record | M, R | PASS, amended |
| R5 | No credential/account required or forwarded | A, P, W | PASS, amended |
| R6 | Ambient secrets and provider text absent from public/operational output | A, G, B sentinel tests | PASS |
| R7 | Shared 36 attempts/minute and collection cap | A | PASS, amended |
| R8 | HTTPS/query2 only; redirects/compression/overrides rejected | A, G | PASS, amended |
| R9 | Bounded daily JSON; symbol/currency/type/timezone/granularity verified | A | PASS, amended |
| R10 | Complete row/date validation before trimming retained input | A, M | PASS, amended |
| R11 | Only dates and closes reach metric kernels | M volume non-reachability | PASS |
| R12 | Same SPY endpoint/calendar; gaps stay missing | M | PASS |
| R13 | Latest completed NYSE session, unknown calendar blocks collection | P, B unsupported-year tests | PASS |
| R14 | 64 observations for full 63D coverage; warmup suppressed from promotion | M, B | PASS |
| R15 | Shared arithmetic, separate public `price_*` and private `nav_*` | M, U | PASS, amended |
| R16 | Simple endpoint returns | M, U | PASS |
| R17 | Non-overlapping 5D excess acceleration | M, U | PASS |
| R18 | 20 simple-return sample volatility, annualized sqrt(252) | M, U | PASS, source label amended |
| R19 | 20-session drawdown, no forecast claim | M, R | PASS |
| R20 | Existing 10-bps regime/hysteresis policy | M, U | PASS |
| R21 | Midrank, at least eight sectors/two horizons, explicit denominator | M, R | PASS |
| R22 | No volume or flow input to metrics, rank or summary | M, R adversarial volume tests | PASS |
| R23 | Eleven rows on every state; missing values distinguished in text | M, R | PASS |
| R24 | Normal=11, partial=8–10 at full history; insufficient/warmup cannot promote | M, S, B | PASS, amended |
| R25 | Derived-only repository/page data and bounded aggregate logs | R, G, B, W exact-two-path staging | PASS |
| R26 | Date/freshness/actual coverage above data; visible Yahoo qualifications and attribution below data | R canonical/order tests, UI amendment | PASS, amended 2026-10-10 |
| R27 | Fixed Yahoo attribution; no invented HF/IEX license | M, R | PASS, amended; permission exception below |
| R28 | One immutable snapshot, shared hash, canonical deterministic pair | M, R, S | PASS |
| R29 | First source failure writes no placeholder | S, B | PASS |
| R30 | Later failure preserves exact pair/id/date; nonzero operational result | S, B auth/stale/calendar tests | PASS |
| R31 | Five exact-commit probes precede separate reviewed activation | P, W, O | PASS; original rollout complete |
| R32 | Private NAV identity, bytes, CLI and no-network boundary retained | U, narrowly scoped public workflow exceptions | PASS |
| R33 | No Telegram, flow, earnings, breadth or narrative feature added | W, G, U | PASS |

## NFR acceptance criteria

| Criterion | Result | Concrete evidence / amendment |
| --- | --- | --- |
| AC-1.1 | PASS, amended | A/P/W require no key, registration or user identity. |
| AC-1.2 | PASS, amended | A rejects injected auth/cookies/hooks/params, disables redirects; no credential transmission. |
| AC-1.3 | PASS | Existing central secret catalogue remains; G/P/B test exact and escaped sentinels before identity exemptions. |
| AC-1.4 | PASS, amended | Invalid client configuration fails before network; 401/403 closed auth rejection without retries/body. |
| AC-1.5 | OPERATOR EXCEPTION | Yahoo attribution constants/schema tested by M/R; public permission stays unverified. No verified-rights assertion. |
| AC-1.6 | PASS | R rejects raw-bar/provider shapes; W stages exactly two derived files; no raw cache/artifact. |
| AC-1.7 | PASS, amended | G pins Yahoo allowlist; free keyless source, existing GitHub Actions/Pages only. |
| AC-1.8 | PASS | R verifies final bytes before S; secret/raw-shape/wording failures block publication. |
| AC-2.1 | PASS, amended | A/G fixed HTTPS host/path/query, 12-symbol allowlist, completed-day period bounds. |
| AC-2.2 | PASS | A per-request connect/read/total limits, overall 120s; B measured overrun cannot promote. |
| AC-2.3 | PASS, amended | A 1 MiB/256 rows, bounded JSON nesting/scalars, equal arrays; compression rejected before body iteration. |
| AC-2.4 | PASS, amended | A shared request lock/budget, 36/minute and total. |
| AC-2.5 | PASS, amended | A concurrency two, at most two retries for allowed failures, bounded backoff and cancellation drain. |
| AC-2.6 | PASS, amended | JSON/no dataframe; 12 × 1 MiB synthetic gate, CPU/RSS evidence in session and five Ubuntu runs. |
| AC-2.7 | PASS | R static page, no client source fetch; all collection belongs to dedicated server-side workflow. |
| AC-3.1 | PASS | A benchmark-first; B first/auth failure preserves no fabricated new page. |
| AC-3.2 | PASS, amended | M 8-sector floor, all eleven including XLRE; B transient one-sector failure publishes partial and exits 2. |
| AC-3.3 | PASS | P pinned NYSE 2026/early closes; B unknown-year zero-network hold/block tests. |
| AC-3.4 | PASS | R canonical verifier; S rejects half/corrupt/mismatched pairs; W verifies before commit and Pages. |
| AC-3.5 | PASS | S/B exact byte and mtime equality on unchanged; git test proves unchanged commit. |
| AC-3.6 | PASS | S recoverable transaction/fault injection; isolated git race test rejects non-fast-forward without changing remote. |
| AC-3.7 | PASS | S/B first failure creates no pair; initial nav ships with validated real bootstrap only. |
| AC-3.8 | PASS | S/B auth, stale, short history, resource and calendar failures preserve prior bytes/date/id; corrupt prior blocks. |
| AC-3.9 | PASS, amended | Keyless auth rejection remains red; O directs requalification without credential/challenge bypass. |
| AC-4.1 | PASS | M/U Decimal and approved kernel numeric contracts. |
| AC-4.2 | PASS, amended | M schema 2/public price types; U private NAV models/serialization unchanged. |
| AC-4.3 | PASS, amended | A uses quote.close, never adjclose; M records provider-close semantics without a stronger adjustment claim. |
| AC-4.4 | PASS, amended | A/M strict unique ascending trading dates; no fill/interpolation or IEX-only claim. |
| AC-4.5 | PASS | M/U property tests: scale, zero excess, acceleration, volatility, drawdown, midrank/order. |
| AC-4.6 | PASS, amended | M fixed eleven records; any unavailable sector suppresses every metric/regime/rank, XLRE no exception. |
| AC-4.7 | PASS | M/R adversarial OHLCV-with-identical-close tests and static call boundary. |
| AC-4.8 | PASS | M property round-trips and provenance/scope/identity invalid-state tests. |
| AC-5.1 | PASS, amended/static | R date/freshness and true 11/11 or partial coverage precede cards/charts; visible source qualifications follow data per 2026-10-10 user instruction. |
| AC-5.2 | PASS | R all eleven rows and text availability reasons on normal/partial/warmup/insufficient states. |
| AC-5.3 | PASS | R half-even two-decimal percent/pp, rank denominator, explicit missing values. |
| AC-5.4 | STATIC PASS; VISUAL WAIVED / NOT_EXECUTED | Semantic/responsive HTML contract retained; no empirical 390×844/desktop clipping/contrast/readability claim. |
| AC-5.5 | PASS | R deterministic observations, disclaimer, no generated narrative or recommendation; public wording guard. |
| AC-6.1 | PASS | P remains manual/read-only, no page writes/schedule/deployment. W is a separate workflow. |
| AC-6.2 | PASS | Five successes on `ec7ac84b`; exact IDs, counts, hash and resource evidence in Step 5 record. |
| AC-6.3 | PASS | Qualified probe commit separate from activation `1a753c7c`, review repair `6b371a1c`. |
| AC-6.4 | PASS, amended | O keyless troubleshooting, rerun/deploy recovery, disable/cancel/remove instructions. No rotation needed. |
| AC-6.5 | PASS | B/P closed bounded summaries; source, attempt freshness, coverage, stored outcome/id/date, counters and timing. |
| AC-6.6 | PASS | Original 6,689-test regression in public closeout; UI exact2e701c42 quality37965908536 passed6,693, Pages37965908527/37966152984 and refresh37966083788 succeeded, live identity confirmed in UI session. |

## Exceptions and residual limits

No open code-review finding remains. Independent review found one P2: unknown-year calendar
failure reported blocked despite valid last-good. The common hold path now preserves correct
status/id/date, with valid/absent/damaged zero-network regression tests and independent recheck.

Two accepted limits remain explicit: provider permission is unverified, and actual viewport
inspection was waived. The 2026 calendar must be reviewed before 2027; until then an unknown
year fails closed and preserves last-good. The cron is configured for trading-week collection;
future executions are monitored in Actions, not claimed as already observed.
