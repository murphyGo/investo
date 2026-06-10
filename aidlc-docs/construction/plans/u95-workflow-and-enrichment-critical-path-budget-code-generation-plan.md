# Code Generation Plan: `u95 workflow-and-enrichment-critical-path-budget`

**Date**: 2026-06-09
**Unit**: u95 workflow-and-enrichment-critical-path-budget
**Stage**: Code Generation
**Status**: Backlog / Planned
**Source**: 2026-06-04/09 daily briefing speed investigation
**Estimated Effort**: ~5-8 h
**Dependencies**:
- u6 infra/CI complete
- u49 market anchor history path complete
- u75 chart-data-externalization-and-mobile-performance complete
- u92 daily-briefing-runtime-observability complete

---

## Problem Statement

The daily briefing job contains non-LLM work that sits on the critical path:

- `.github/workflows/daily-briefing.yml` installs uv, Python, Cairo packages, project runtime dependencies, and Claude CLI every run.
- `_load_market_anchors_for_run` performs a separate Yahoo history fetch before segment generation starts. This is best-effort enrichment, but a slow or 429-prone network path can delay every segment.
- `_stage_prepare_segment_visual_assets` prepares visuals one segment at a time after generation. Visual failures already degrade to text-only, but preparation still consumes critical-path wall-clock.

These are not the primary LLM bottlenecks, but they are recurring runtime costs that accumulate after the pipeline has grown.

## Goal

Reduce non-LLM critical-path time while preserving zero-cost operation and graceful degradation:

- cache workflow setup where GitHub Actions supports it,
- minimize packages installed for OG-card PNG conversion,
- bound market-anchor history fetch impact,
- run visual preparation under bounded per-segment concurrency,
- keep text-only publish behavior on enrichment failure.

## Existing Coverage / Deduplication

- u6 owns cron, secrets, Pages deploy, and workflow structure. u95 changes setup efficiency only; it does not change triggers, permissions, or exit-code mapping.
- u49 owns market-anchor computation and u70 reconciles anchor values across surfaces. u95 only bounds history fetch cost and graceful omission.
- u50/u75 own chart rendering and sidecar payloads. u95 does not redesign chart UI or sidecar schema.
- u19/u24/u86 own visual asset policy and provenance. u95 does not add visual sources or change licensing gates.

## Scope Boundary

In scope:
- Add GitHub Actions caching for uv and npm/Claude CLI installation.
- Reduce Cairo package installation to runtime-required packages.
- Add a bounded budget for Yahoo history anchor fetch.
- Add bounded per-segment visual preparation concurrency.
- Add summary/log evidence through u92 timing surfaces.

Out of scope:
- Changing cron schedule or workflow permissions.
- Adding paid cache services, new secrets, or external workers.
- Changing visual asset policy, curated asset selection, or OpenAI visual opt-in behavior.
- Changing chart sidecar schema or public chart UI.
- Backfilling existing archive assets.

## Stage Decision

- **Functional Design — SKIP.** This is infrastructure/runtime budget refinement over existing surfaces.
- **NFR Requirements — REQUIRED, focused.** Workflow caching and bounded enrichment touch NFR-001 performance, NFR-002 zero-cost, NFR-003 graceful degradation, and NFR-007 secret handling.

## Implementation Steps

### Step 1 — workflow setup cache

- [ ] Update `.github/workflows/daily-briefing.yml` to enable uv cache keyed by `uv.lock`.
- [ ] Add Node setup with npm cache before installing `@anthropic-ai/claude-code`.
- [ ] Keep the Claude CLI installation command explicit and keep `claude --version` preflight.
- [ ] Add a workflow text test or static check that pins no new secrets and no paid services.

### Step 2 — Cairo install minimization

- [ ] Verify the OG-card PNG preflight only needs runtime Cairo libraries.
- [ ] Replace broad install packages with the minimal package set that still passes the existing `cairosvg.svg2png` preflight.
- [ ] Keep `sudo apt-get update` and install in one step.
- [ ] Document the package rationale in the workflow comment.

### Step 3 — market-anchor budget

- [ ] Add a local budget around `_load_market_anchors_for_run` in `src/investo/orchestrator/stage_context.py`.
- [ ] Keep graceful degrade: on timeout or fetch failure, return empty anchors and empty history.
- [ ] Expose elapsed and degraded reason through u92 logs.
- [ ] Preserve `_build_kr_anchors_from_items` domestic fallback behavior from collected items.

### Step 4 — visual preparation concurrency

- [ ] Add a bounded helper in `_stage_prepare_segment_visual_assets`.
- [ ] Default worker count: 1 for behavior-compatible rollout.
- [ ] Accepted env var: `INVESTO_VISUAL_PREP_CONCURRENCY` values `1`, `2`, `3`; invalid values fall back to 1 with warning.
- [ ] Preserve existing all-visual failure behavior: visual asset error sets `visual_assets_failed=True` and publishes text-only.
- [ ] Preserve asset path ordering by `SEGMENT_ORDER`.

### Step 5 — verification and summary

- [ ] Add tests for workflow YAML text guards.
- [ ] Add tests for market-anchor timeout returning empty anchors/history.
- [ ] Add tests for visual-prep ordering and failure fallback.
- [ ] Confirm u92 summary surfaces show `generate:context` and `visual_assets` timing changes.

## Acceptance Criteria

1. Daily briefing workflow uses uv and npm caching without new secrets, paid services, or trigger changes.
2. OG-card PNG conversion preflight still passes with the reduced Cairo package set.
3. Market-anchor history fetch cannot delay segment generation beyond its configured budget.
4. Market-anchor timeout or Yahoo 429 still produces a publishable briefing with omitted anchor/chart history.
5. Visual asset preparation can run with concurrency 2 or 3 and returns asset paths in deterministic segment order.
6. Visual preparation failure still degrades to text-only publish without failing the pipeline.
7. Workflow, anchor, and visual timing changes are visible through u92 logs or summary rows.

## Tests / Validation

- Static workflow tests in `tests/unit/orchestrator/` or `tests/unit/workflows/` following existing workflow text-check style.
- `tests/unit/sources/test_yfinance_history.py` and `tests/unit/orchestrator/test_stage_generate.py` for anchor budget/degrade behavior.
- `tests/unit/publisher/test_chart_assets.py` or visual asset tests for visual-prep failure and path ordering.
- Local gate: `uv run pytest tests/unit/orchestrator tests/unit/sources tests/unit/publisher -q`, `uv run ruff check .github src tests`, `uv run mypy --strict src`.
- Live verification after implementation: compare two GitHub Actions runs, one before u95 and one after u95, using u92 summary timing rows.

## Non-Goals

- Moving daily briefing generation off GitHub Actions.
- Adding a service, database, or cache server.
- Changing Claude Code authentication.
- Changing public markdown layout.
- Changing visual asset licensing or curated asset manifests.
