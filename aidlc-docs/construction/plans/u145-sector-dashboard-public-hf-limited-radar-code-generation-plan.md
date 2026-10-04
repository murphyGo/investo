# Code Generation Plan: `u145 sector-dashboard-public-hf-limited-radar`

**Date**: 2026-07-22
**Unit**: u145 sector-dashboard-public-hf-limited-radar
**Stage**: Code Generation
**Status**: Step 5 complete — Yahoo public replacement reviewed, pushed and qualified in 5/5 exact-commit Actions runs; Step 6 separate activation remains unstarted
**Dependencies**: u139 complete; u140 strict gate unchanged; Yahoo requires no API key

## Active Yahoo amendment — 2026-10-04/05

The user selected **public** Yahoo implementation after being told permission remains
unverified. The [source amendment](../u145-sector-dashboard-public-hf-limited-radar/source-qualification/2026-10-04-yahoo-public-amendment.md)
supersedes HF-specific scope/invariants/Steps 0–5 below. Those sections are original historical
evidence; they are not an instruction to restore HF or require a key. Free-only remains binding.

- [x] Replace production collector with bounded, no-key Yahoo daily JSON.
- [x] Switch schema/provenance/price labels and include XLRE in all eleven sector calculations.
- [x] Replace provider-specific tests/guard/benchmark and remove the HF workflow secret.
- [x] Local production path: 12/12 symbols, 11 comparable, target/as-of 2026-10-02, qualified.
- [x] Local full-window 1 MiB-response resource gate: pass, 12 requests, 140 rows/response.
- [x] Complete regression, static/site checks and independent review (5,543 full + 160 final focused).
- [x] Push reviewed implementation `ec7ac84b` and collect five successful exact-commit Actions probes.
- [ ] Prepare the separate Step 6 activation after qualification; no activation in this slice.

No public-use license is invented. Viewport waiver remains `WAIVED / NOT_EXECUTED`.


## Original HF Stage Decision (historical)

- Application Design: **COMPLETE** on 2026-07-22.
- Functional Design: **COMPLETE, amended 2026-09-02** — R1-R33, E1-E19, I1-I7, C1-C7,
  L1-L12, with signed daily Parquet transport.
- NFR/Security Requirements: **COMPLETE, amended 2026-09-02** — AC-1.1 through AC-6.6 and
  TS-1 through TS-8, with a pinned sector-only Parquet reader.
- Code Generation: **ACTIVE — STEP 5**. The operator added `HF_DATA_API_KEY`, final
  sanitized probe `33578785358` qualified the live contract, and `gogo` approved continued
  construction. Public sibling models, shared kernels, the closed bounded HF adapter, and
  derived-only public snapshot computation, renderer/verifier, and derived-only store are
  implemented. On 2026-09-27 the user waived actual 390x844 and desktop viewport validation
  after repeated Browser failures. Step 4 is closed with that explicit exception; visual
  execution remains `NOT_EXECUTED`, not PASS. All non-visual gates remain binding.

## Scope Boundary

In scope:

- HF daily bars for SPY plus ten supported sector ETFs.
- Source-neutral kernel extraction behind unchanged u139 NAV wrappers.
- Public IEX-price metrics, regime/rank, explicit XLRE unavailable, provenance/attribution.
- Derived-only deterministic Markdown/JSON pair and last-good state.
- Dedicated probe workflow, then separate schedule/Pages activation after five successes.

Out of scope:

- Account creation, identity/email verification, automatic key rotation.
- XLRE proxy/fallback, consolidated-market claims, volume score, dollar volume, flow.
- Raw provider history retention, direct IEX PCAP, TradingView, paid source fallback.
- Telegram, actual flow, earnings actual, constituent breadth, narrative/LLM integration.
- Coupling u145 qualification to the daily briefing workflow.

## Fixed Contracts

1. u140 remains blocked; u145 is a limited sibling and does not satisfy strict source gates.
2. HF source v1 implies `iex_venue_sample`, `consolidated_market_data=False`, fixed 11-symbol
   request set, XLRE value-free unavailable record, and both mandatory attributions.
3. Volume is parse-validation input only and cannot reach any metric/rank/regime/summary output.
4. Existing u139 types/functions/artifact bytes remain compatible; only generic math kernels
   are shared.
5. Public artifacts are derived-only and form one validated snapshot-id pair.
6. First publish fails closed. Last-good hold preserves bytes/as-of and remains operationally red.
7. Probe code/workflow lands before and separately from scheduled/Pages activation.
8. Runtime transport is the exact X-API-Key token request followed by one validated same-host
   signed daily Parquet download; `pyarrow==25.0.1` is isolated to the sector workflow.

## Planned File Surfaces

- `src/investo/models/sector.py` and/or `src/investo/models/sector_public.py`
- `src/investo/sector_dashboard/metric_kernels.py`
- `src/investo/sector_dashboard/hf_data.py`
- `src/investo/sector_dashboard/public_metrics.py`
- `src/investo/sector_dashboard/public_render.py`
- `src/investo/sector_dashboard/public_store.py`
- `scripts/build_sector_dashboard_public.py`
- `.github/workflows/sector-dashboard-probe.yml`
- later activation only: scheduled workflow, `mkdocs.yml`, `site_docs/sectors/`
- focused unit/property/integration/security/workflow tests under `tests/`

## Implementation Steps

### Step 0 — Credentialed source-contract qualification — EVIDENCE COMPLETE

Prerequisite: operator-owned HF account, verified email, and current API key.

- [x] Confirm authenticated endpoint path/parameters, header, content type, status/error shapes,
  response order, pagination/range behavior, and row identity.
- [x] Prove SPY plus all ten supported sectors each provide at least 64 comparable daily rows;
  reconfirm XLRE absence without treating it as a request failure.
- [x] Reconcile official docs with payload evidence for raw/split/dividend adjustment semantics.
- [x] Measure response sizes, request count, duration, as-of/freshness, zero-trade/zero-volume
  behavior, live 401/404 behavior, and official 403/429 policy; reserve malformed/empty and
  non-induced throttle shapes for synthetic adapter tests.
- [x] Record only sanitized schema/semantics/count/date evidence; commit no raw response/bar data.
- [x] If any binding right/cost/supported-symbol/IEX-label premise changes, stop and amend design.

2026-09-02 pre-probe finding: the current official API no longer exposes the planned daily JSON
row endpoint. Daily bars now use `GET /download-token/{ticker}` followed by a short-lived signed
CSV/Parquet download URL; `/bars/{ticker}` serves the full 1-minute Parquet file. The manual,
read-only Step 0 workflow records only sanitized schema/count/date/size evidence. The 2 MiB/10,000
row envelope, fixed request path, signed-token handling, and in-memory parser contract therefore
required the Step 0A amendment recorded below before Step 1.

Final evidence: `33578785358` passed on head `a01de8f` with 11/11 requested symbols, one common
`2026-08-31` latest date, 2,061-5,954 rows per symbol, 97,924-248,536 bytes per response,
2,334,018 bytes total, strictly ascending unique dates, zero invalid OHLC/negative-volume/
zero-volume daily rows, and latest source `iex`. XLRE returned 404 from both public metadata and
the authenticated token endpoint. `X-API-Key` daily Parquet returned 200; bearer returned 401;
the documented daily CSV contract returned 404. Full sanitized record:
`source-qualification/2026-09-02-hf-step0.md`.

Step 0 transport/schema evidence is complete and an operator-owned secret path is available.

### Step 0A — Signed daily Parquet design amendment — COMPLETE

- [x] Record operator approval (`gogo`, 2026-09-02).
- [x] Amend Functional transport, credential, schema, adjustment, and retention contracts.
- [x] Amend NFR request-count, signed-URL, response, dependency, and test contracts.
- [x] Approve pinned `pyarrow==25.0.1` only for the sector workflow; forbid pandas/dataframes.
- [x] Keep the 2 MiB production response ceiling and reserve 8 MiB for probe observation only.
- [x] Keep Pages navigation, schedule, repository writes, Telegram, and briefing coupling off.

### Step 1 — Public models and shared kernels

- [x] Add sibling public bar/bundle/metric/record/provenance/snapshot/outcome types.
- [x] Extract source-neutral kernels behind byte-compatible u139 `nav_*` wrappers.
- [x] Add golden u139 compatibility tests and TS-1/TS-2 PBT.
- [x] Add XLRE structural-absence and market-scope/source-id invariants.

Implementation note: u145 uses `PublicCoverageSummary` rather than broadening the frozen u139
type. This preserves u139 bytes while representing the approved 6-63-row public warming window
and 64-row full-metric threshold. The shared volatility kernel keeps the return convention
explicit: u139 wrappers select their existing log-return contract; future u145 price wrappers
select the approved simple-return contract.

### Step 2 — Bounded HF adapter

- [x] Add fixed host/endpoint/request-set client with injected `httpx.AsyncClient`.
- [x] Implement token-then-signed-download with a fixed User-Agent, exact same-host/path
  validation, no redirects, and no API-key forwarding to the download.
- [x] Add header-only key validation, central redaction entry, signed-URL redaction,
  response/resource limits, shared 100-call/minute budget, 22-call clean-run accounting, and
  closed codes.
- [x] Decode only the accepted seven-column shape through pinned PyArrow; use synthetic Parquet.
- [x] Complete TS-3/TS-4 and no-paid/fallback negative tests.

Implementation note: the adapter owns no HTTP client and exposes no runtime endpoint or request
set. It rejects observing hooks, default query parameters, pre-existing cookies, and mismatched
budgets before the first call; scrubs inherited request headers; clears provider cookies after
every response; and returns only normalized public DTOs or closed issue codes. The CI guard pins
the single HF identity, immutable daily/Parquet/clean query, exact token/download call sites, and
one direct build/send path while rejecting secondary clients, imports, constructed hosts,
indirect bound methods, and reflection. PyArrow remains an exact optional `sector` dependency,
and quality CI installs that extra so schema tests cannot skip.

### Step 3 — Public snapshot computation

- [x] Resolve SPY-first as-of/freshness/coverage and construct source-neutral close bundles.
- [x] Compute IEX-price metrics, regime, and rank through shared kernels.
- [x] Prove volume non-reachability and explicit missing reasons.
- [x] Build complete provenance/attribution and deterministic snapshot id.

Implementation note: snapshot computation retains only the final 64 dates and closes, resolves
freshness against the versioned 2026 NYSE calendar, and suppresses every metric/rank/regime when
SPY freshness or the eight-sector coverage floor fails. Warming coverage exposes only approved
1-day/5-day return and excess slots. Full coverage uses the shared simple-return, relative
acceleration, realized-volatility, drawdown, midrank, and `sector-regime-v1` kernels. Every one
of the eleven fixed cards remains represented; XLRE is always value-free
`provider_unavailable`. Canonical sorted compact JSON excluding `snapshot_id` produces the
SHA-256 identity. Tests prove OHLCV changes outside close cannot affect bundles or snapshots and
pin exact calendar/history/provider missing reasons. Fresh-eyes review closed all findings and
reported zero remaining Critical, High, or Medium issues.

### Step 4 — Renderer and derived-only store

- [x] Render C1-C7 with first-viewport qualification and exactly eleven cards.
- [x] Build/verify deterministic Markdown/JSON pair with parsed canonical JSON, exact snapshot-id
  equality, canonical-byte checks, and raw/secret/wording guards.
- [x] Implement idempotent promotion, pair mismatch rejection, first-publish fail-closed,
  recoverable pre-git behavior, and last-good hold.
- [x] Complete the non-viewport TS-5/TS-6 cases and strict built-HTML semantic/static checks.
- [x] **WAIVED by user on 2026-09-27; NOT_EXECUTED** — actual 390x844 and desktop Browser
  validation. This checkbox records the approved disposition, not a visual test pass. The
  environment reported no available browser. The 2026-09-09 current-main revalidation again
  returned `AGENT_UNAVAILABLE`. A later 2026-09-09 retry failed during Browser bootstrap because
  the referenced `26.901.51231/scripts/browser-service.mjs` is absent; the official Chrome
  native-host diagnostic also reports `exists=false`, `correct=false`. Five local synthetic
  page states pass strict build and HTML structure checks, but actual viewport acceptance
  remains unexecuted. See `docs/sessions/2026-09-09-u145-code-generation-step4-recovery.md`.

2026-09-22 resumption: Step 1–4 was integrated onto current main `c286f500` in the persistent
worktree `.tmp/u145-resume-20260922`, preserving the prior recovery worktree. Review repaired a
false missing-metric label and loss of rollback backup during failed cleanup, with regression
cases for partial/complete backup removal, marker removal, and a second interruption during
restore. Five synthetic states again pass strict build/static checks. Browser startup still
fails on an absent service bundle and the Chrome native-host diagnostic remains negative;
viewport acceptance is not executed. Evidence and final checks:
`docs/sessions/2026-09-22-u145-step4-resume-and-repair.md`.

2026-09-27 viewport retry: rebuilt all five synthetic previews successfully and verified local
HTTP 200 responses. Actual Browser startup fails on the absent
`26.915.31945/scripts/browser-service.mjs`; the official Chrome native-host diagnostic still
reports `exists=false`, `correct=false`. The user was asked to reinstall Browser through the
app UI and restart Codex/Chrome. No actual viewport measurement or screenshot was produced;
the Step 4 checkbox remains open. The pending 20-view acceptance matrix and current evidence
are recorded in `docs/sessions/2026-09-27-u145-viewport-retry.md`.

2026-09-27 user decision, superseding the open-gate statements above: the user asked
`아무리 해도 안되는데, 그냥 검증 스킵할 수 없음?`. The actual Browser viewport check is
waived for u145 Step 4 and its pre-Pages visual prerequisite under NFR AC-5.4. Step 4 is closed
with exception and Step 5 may proceed without Browser recovery. Existing static checks,
five production-adapter probes, integration/security/data checks, and separate Step 6 Pages
activation remain required. No visual pass, blanket test waiver, or deployment approval is
implied. Decision: `docs/sessions/2026-09-27-u145-viewport-waiver.md`.

### Step 5 — Isolated probe workflow

**Yahoo closeout (2026-10-05): complete, 5/5 passed on `ec7ac84b`.** See
`docs/sessions/2026-10-05-u145-yahoo-public-source.md` and its Actions evidence.
The HF implementation details and 0/5 outcome below are historical, superseded by this closeout.

- [x] Add manual workflow with read-only permissions, current operator secret, bounded summary,
  zero public writes, no Pages, no Telegram, and no daily briefing invocation.
- [x] Run focused/full gates plus TS-7/TS-8 benchmark.
- [x] Execute five successful isolated GHA probes and record run ids/evidence (Yahoo replacement, 2026-10-05).

Final validation completed on 2026-10-03 against implementation `90f09d99`: 5,563 full-suite
tests and 158 focused adapter/metrics/probe tests passed, along with Ruff/format, strict mypy,
policy/site gates and the synthetic 11 x 10,000-row benchmark. Independent review approved
both live-found repairs: bounded retained history and the documented token metadata envelope.
The unchanged Ubuntu resource gate passed in four runs after the memory repair, including
three runs on the final implementation. The user-approved branch was committed and pushed.
Live successes remain 0/5: one final-code run collected all eleven symbols but was stale;
two later runs hit retryable token-server failures. Unauthenticated HTTP 503 was independently
reproduced while public metadata remained available. Evidence:
`docs/sessions/2026-10-03-u145-step5-closeout.md` and its aggregate JSON.

2026-10-04 source update: the actual token response identifies `data_paused` due to dataset
restructuring, without a recovery date. The user authorized provider replacement and then
explicitly limited candidates to free providers. No examined replacement currently clears
public-use and working-delivery qualification. Do not repeat identical HF qualification
batches while the pause persists. Replacement implementation remains pending source acceptance;
the user waiver and separate Step 6 boundary persist. Findings and exact migration surfaces:
`aidlc-docs/construction/u145-sector-dashboard-public-hf-limited-radar/source-qualification/2026-10-04-free-provider-requalification.md`.

Step 5 execution scope (2026-09-27): the existing Step 0 workflow is upgraded to call
`scripts/build_sector_dashboard_public.py --probe-only` through the production adapter,
`public_probe.py` composition/evidence, shared public metrics and canonical renderer. No write
mode is added. `scripts/benchmark_sector_dashboard_public.py` owns TS-8 synthetic maximum-shape
evidence before the secret-bearing live step. Qualification requires all eleven supported
symbols with ten comparable sectors; eight/nine-sector partial output remains a product
contract but does not qualify the five-run gate. Request counters distinguish accepted bounded
HTTP responses from final symbol success. These are implementations of existing AC-2.6 and
AC-6.1..6.6, not new public product behavior. Runbook: `docs/sector-dashboard-probe-runbook.md`.

### Step 6 — Separate Pages activation

Prerequisite: Step 5 five-run evidence complete.

- [ ] Add scheduled collection/public pair staging in a dedicated sector workflow.
- [ ] Add `site_docs/sectors/` navigation and Pages validation.
- [ ] Prove a fresh publish, unchanged run, one transient-sector partial run, auth-expiry
  last-good run, and first-publish failure in isolated integration evidence.
- [ ] Keep Telegram and daily briefing coupling absent.

### Step 7 — Quality gates and closeout

- [ ] Run focused tests/PBT, full pytest, Ruff check/format, strict mypy, no-paid guard, leak
  scans, workflow checks, u139 compatibility, `mkdocs build --strict`, and resource benchmark.
- [ ] Cross-check every Functional/NFR AC and record exact run ids, hashes, request/runtime,
  memory, attribution, freshness, and negative-path evidence.
  Report AC-5.4 visual execution as `WAIVED / NOT_EXECUTED` with the 2026-09-27 user decision;
  do not count it as empirically verified or reopen it solely because Browser remains broken.
- [ ] Update AIDLC state only after Pages evidence is current and complete.

## Current Gate

The active source is Yahoo under the operator exception. Implementation commit
`ec7ac84b927a78e5f3e5f0f3dac6494bb9a7ac6b` passed independent review, full regression and
final focused checks. Actions runs `37213980547`, `37214093128`, `37214127663`, `37214182986`
and `37214258087` all passed resources and qualified fresh 12/12-symbol production data.
Step 5 is complete. Step 6 Pages/navigation/schedule implementation and activation remain
separate and unstarted. No main merge or public sector artifacts were created. Browser
recovery and HF account/key recovery are not prerequisites. Telegram and daily-briefing
coupling remain outside this unit.

The following credential notes concern the superseded HF implementation only.

Historical verification on 2026-07-22 confirmed both boundaries without reading any secret
value:

- local `HF_DATA_API_KEY`: absent;
- GitHub Actions secret-name inventory: no `HF_DATA_API_KEY` entry.

Current verification on 2026-09-02 confirmed the repository secret name is present. The value
was not and cannot be read back through GitHub's secret inventory API.

Final live verification on 2026-09-02 used the secret only inside read-only workflow
`33578785358`; Actions masked the value, no raw bar or signed URL was retained, and the workflow
completed successfully in 24 seconds.
