# Code Generation Plan: `u55 numeric-freshness-and-market-fact-gates`

**Date**: 2026-05-13
**Unit**: u55 numeric-freshness-and-market-fact-gates
**Stage**: Code Generation
**Status**: 📋 Planned
**Source**: 2026-05-13 10-subagent evaluation of generated market briefings, deduplicated against u51/u52/u53.
**Estimated Effort**: ~4-5 h
**Dependencies**:
- u25 summary-fidelity-and-content-trust (numeric invention avoidance and first-viewport trust).
- u32 trust-traceability-deep-dive (numeric self-check foundation).
- u49 deterministic-market-anchor (source-backed market fact anchors).
- u50 lightweight-charts-embed (history source reuse).

---

## Deduplication Boundary

Excluded because already owned elsewhere:
- u51: visual emphasis of numbers via bold wrapping.
- u53: adding missing domestic flow and sector/macro ETF inputs.
- u52: previous-day event carryover.

This unit owns **whether a number/date/direction is true, fresh, and source-backed**.

---

## Goal

Upgrade the quality system from "numbers exist" to "core numbers are verified against source items or market anchors", and detect stale archive/quality pages before they look current.

Observed failures from 2026-05-11 briefing review:
- Domestic KOSPI level is repeated while structured index source is 0 items.
- Crypto first-viewport text contains date-token corruption (`5/65/7`).
- Quality KPI reports 100% figure presence without verifying source equivalence.
- Local latest archive can become stale relative to the current market date.

---

## Definition of Done

- [ ] Core market claims require source-backed values or explicit `확인 필요` downgrade.
- [ ] `figures_presence` and `figures_verified` are separate KPI concepts.
- [ ] Date-token corruption and impossible date ranges are detected before publish.
- [ ] Archive and quality-page freshness are measured per segment market calendar.
- [ ] Unverified/stale facts produce operator-visible warnings and reader-visible status where appropriate.

---

## Steps

### Step 1 — Core numeric claim inventory

- [ ] Define core claim patterns: index level, close/open/high/low, percent move, yield, FX, BTC/ETH price, date ranges.
- [ ] Map claim patterns to source categories and market anchor fields.
- [ ] Establish tolerance rules for Decimal/string formatting differences.

### Step 2 — Numeric verification engine

- [ ] Extend `numeric_self_check.py` or add a sibling helper for `claim -> source item -> parsed value -> tolerance`.
- [ ] Emit per-claim verification state: verified, unverified, conflict, not-core.
- [ ] Keep non-core numbers as warnings rather than hard blockers.

### Step 3 — Date and direction sanity gates

- [ ] Add date-token anomaly checks for malformed date spans such as `5/65/7`.
- [ ] Validate first-viewport action/direction tag against market anchor direction when anchors exist.
- [ ] Detect "ATH" or "52w high" claims that conflict with anchor metadata.

### Step 4 — Freshness gate

- [ ] Compare latest archive date and `site_docs/quality.md` target date with segment-specific market calendar expectations.
- [ ] Add stale status to quality page and operator summary.
- [ ] Do not fail unrelated segments when only one segment is stale; report segment-scoped stale state.

### Step 5 — Tests and gates

- [ ] Unit tests for verified/conflict/unverified numeric claims.
- [ ] Unit tests for date corruption and impossible ranges.
- [ ] Orchestrator tests for stale archive/quality page policy.
- [ ] Run `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy --strict src/`, `uv run pytest -q`, `uv run mkdocs build --strict`.

---

## Out of Scope

- Reader formatting and number bolding (u51).
- New data-source adapters (u53).
- Compliance language gate (u56).
- Segment narrative scope reconciliation (u57).

