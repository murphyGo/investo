# Code Generation Plan: `u145 sector-dashboard-public-hf-limited-radar`

**Date**: 2026-07-22
**Unit**: u145 sector-dashboard-public-hf-limited-radar
**Stage**: Code Generation
**Status**: Blocked before Step 0 credentialed source qualification
**Dependencies**: u139 complete; u140 strict gate remains blocked; operator-owned HF key required

## Stage Decision

- Application Design: **COMPLETE** on 2026-07-22.
- Functional Design: **COMPLETE** — R1-R33, E1-E19, I1-I7, C1-C7, L1-L12.
- NFR/Security Requirements: **COMPLETE** — AC-1.1 through AC-6.6 and TS-1 through TS-8.
- Code Generation: **BLOCKED** until Step 0 can use an operator-owned verified HF account/key.

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

### Step 0 — Credentialed source-contract qualification — BLOCKED

Prerequisite: operator-owned HF account, verified email, and current API key.

- [ ] Confirm authenticated endpoint path/parameters, header, content type, status/error shapes,
  response order, pagination/range behavior, and row identity.
- [ ] Prove SPY plus all ten supported sectors each provide at least 64 comparable daily rows;
  reconfirm XLRE absence without treating it as a request failure.
- [ ] Reconcile official docs with payload evidence for raw/split/dividend adjustment semantics.
- [ ] Measure response sizes, request count, duration, as-of/freshness, zero-trade/zero-volume
  behavior, malformed/empty behavior, 401/403, and 429 policy.
- [ ] Record only sanitized schema/semantics/count/date evidence; commit no raw response/bar data.
- [ ] If any binding right/cost/supported-symbol/IEX-label premise changes, stop and amend design.

Exit gate: all unknown payload assumptions are resolved and an operator-owned secret path is
available for isolated tests. Until then, no adapter/model implementation begins.

### Step 1 — Public models and shared kernels

- [ ] Add sibling public bar/bundle/metric/record/provenance/snapshot/outcome types.
- [ ] Extract source-neutral kernels behind byte-compatible u139 `nav_*` wrappers.
- [ ] Add golden u139 compatibility tests and TS-1/TS-2 PBT.
- [ ] Add XLRE structural-absence and market-scope/source-id invariants.

### Step 2 — Bounded HF adapter

- [ ] Add fixed host/endpoint/request-set client with injected `httpx.AsyncClient`.
- [ ] Add header-only key validation, central redaction entry, response/resource limits, shared
  rate/retry/concurrency budget, and closed diagnostic codes.
- [ ] Normalize only the accepted Step 0 shape; use synthetic schema-equivalent fixtures.
- [ ] Complete TS-3/TS-4 and no-paid/fallback negative tests.

### Step 3 — Public snapshot computation

- [ ] Resolve SPY-first as-of/freshness/coverage and construct source-neutral close bundles.
- [ ] Compute IEX-price metrics, regime, and rank through shared kernels.
- [ ] Prove volume non-reachability and explicit missing reasons.
- [ ] Build complete provenance/attribution and deterministic snapshot id.

### Step 4 — Renderer and derived-only store

- [ ] Render C1-C7 with first-viewport qualification and exactly eleven cards.
- [ ] Build/verify deterministic Markdown/JSON pair and raw/secret/wording guards.
- [ ] Implement idempotent promotion, pair mismatch rejection, first-publish fail-closed,
  recoverable pre-git behavior, and last-good hold.
- [ ] Complete TS-5/TS-6 and mobile/static accessibility checks.

### Step 5 — Isolated probe workflow

- [ ] Add manual workflow with read-only permissions, current operator secret, bounded summary,
  zero public writes, no Pages, no Telegram, and no daily briefing invocation.
- [ ] Run focused/full gates plus TS-7/TS-8 benchmark.
- [ ] Execute five successful isolated GHA probes and record run ids/evidence.

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
- [ ] Update AIDLC state only after Pages evidence is current and complete.

## Current Blocker

HF requires accurate account registration, email verification, and an API key that expires
every 30 days. No operator-owned key is available in the current environment. Creating an
identity/account or completing email verification is outside Investo's autonomous code scope.
Therefore Step 0 payload qualification—and all implementation that depends on it—cannot begin.

Live verification on 2026-07-22 confirmed both boundaries without reading any secret value:

- local `HF_DATA_API_KEY`: absent;
- GitHub Actions secret-name inventory: no `HF_DATA_API_KEY` entry.
